<template>
  <div class="galleryDisplay uk-padding uk-padding-remove-top">
    <!-- Gallery nav bar -->
    <nav
      class="gallery-navbar uk-navbar-container uk-navbar-transparent"
      uk-navbar="mode: click"
    >
      <!-- Left side controls -->
      <div
        class="uk-navbar-left uk-padding-remove-top uk-padding-remove-bottom"
      >
        <ul class="uk-navbar-nav">
          <li :class="[sortDescending ? 'uk-active' : '']">
            <a class="uk-icon" href="#" @click="sortDescending = true">
              <i class="material-icons">keyboard_arrow_down</i>
            </a>
          </li>
          <li :class="[!sortDescending ? 'uk-active' : '']">
            <a class="uk-icon" href="#" @click="sortDescending = false">
              <i class="material-icons">keyboard_arrow_up</i>
            </a>
          </li>
          <li>
            <a href="#">Filter</a>
            <div
              class="uk-navbar-dropdown"
              :class="{
                'uk-light uk-background-secondary':
                  $store.state.globalSettings.darkMode
              }"
            >
              <ul class="uk-nav uk-navbar-dropdown-nav">
                <form class="uk-form-stacked">
                  <div
                    v-for="tag in allTags"
                    :key="tag"
                    class="uk-margin-small"
                  >
                    <label>
                      <input
                        :id="tag"
                        v-model="checkedTags"
                        class="uk-checkbox"
                        type="checkbox"
                        :value="tag"
                        checked
                      />
                      {{ tag }}
                    </label>
                  </div>
                </form>
              </ul>
            </div>
          </li>
        </ul>
      </div>

      <!-- Right side buttons -->
      <div class="uk-navbar-right">
        <div class="uk-grid">
          <div>
            <button
              type="button"
              class="uk-button uk-button-default uk-width-1-1"
              @click="updateCaptures()"
            >
              Refresh Captures
            </button>
          </div>
          <div>
            <ZipDownloader :capture-ids="Object.keys(filteredCaptures)" />
          </div>
        </div>
      </div>
    </nav>

    <!-- Gallery -->
    <div
      v-if="$store.getters.ready"
      class="uk-padding-remove-top"
      uk-lightbox="toggle: .lightbox-link"
    >
      <!-- Folder heading -->
      <div
        v-if="galleryFolder"
        class="gallery-folder-heading uk-flex uk-flex-middle"
      >
        <a
          href="#"
          class="uk-icon uk-margin-remove"
          @click="galleryFolder = ''"
        >
          <i class="material-icons">arrow_back</i>
        </a>
        <div class="uk-margin-left">
          <h3 class="uk-margin-remove uk-margin-left">
            <b>SCAN</b>
            {{ allScans[galleryFolder].metadata.image.name }}
          </h3>
        </div>
      </div>

      <!-- Gallery capture cards -->
      <div class="gallery-grid">
        <div v-for="item in sortedItems" :key="item.metadata.id">
          <scanCard
            v-if="'isScan' in item"
            :metadata="item.metadata"
            :thumbnail="item.thumbnail"
            :captures="item.captures"
          />
          <captureCard v-else :capture-state="item" />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import captureCard from "./galleryComponents/captureCard.vue";
import scanCard from "./galleryComponents/scanCard.vue";

import ZipDownloader from "./galleryComponents/zipDownloader";

// Export main app
export default {
  name: "GalleryDisplay",

  components: {
    captureCard,
    scanCard,
    ZipDownloader
  },

  data: function() {
    return {
      captures: [],
      checkedTags: [],
      sortDescending: true,
      galleryFolder: "",
      scanTag: "scan",
      unwatchStoreFunction: null
    };
  },

  computed: {
    capturesUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/captures`;
    },
    allTags: function() {
      // Return an array of unique tags across all captures
      var tags = [];
      for (var capture of this.captures) {
        for (var tag of capture.metadata.image.tags) {
          if (!tags.includes(tag)) {
            tags.push(tag);
          }
        }
      }
      return tags.sort();
    },

    noScanCaptures: function() {
      // List of captures that are not part of a scan
      var captures = [];
      for (var capture of this.captures) {
        // Add to capture list if matched
        if (!capture.metadata.dataset) {
          captures.push(capture);
        }
      }

      return captures;
    },

    allScans: function() {
      // List of scans as capture-like objects
      var scans = {};

      for (var capture of this.captures) {
        var annotations = capture.metadata.image.annotations;
        var tags = capture.metadata.image.tags;
        var dataset = capture.metadata.dataset;

        if (dataset) {
          var id = dataset["id"];

          // If this scan ID hasn't been seen before
          if (!(id in scans)) {
            scans[id] = {};
            scans[id].isScan = true;
            scans[id].captures = [];
            scans[id].metadata = {
              image: {
                name: dataset.name,
                acquisitionDate: dataset.acquisitionDate,
                id: dataset.id,
                tags: [],
                annotations: {}
              },
              type: dataset.type
            };
          }

          // Add the capture object to the scan
          scans[id].captures.push(capture);

          // Add missing scan metadata, prioritising first capture
          for (var key of Object.keys(annotations)) {
            if (!(key in scans[id].metadata.image.annotations)) {
              scans[id].metadata.image.annotations[key] = annotations[key];
            }
          }

          // Append missing tags
          for (var tag of tags) {
            if (!scans[id].metadata.image.tags.includes(tag)) {
              scans[id].metadata.image.tags.push(tag);
            }
          }

          // Create a preview thumbnail
          if (!("thumbnail" in scans[id])) {
            scans[
              id
            ].thumbnail = `${capture.links.download.href}?thumbnail=true`;
          }
        }
      }
      return scans;
    },

    scanList: function() {
      // List of scans, obtained from this.allScans values
      return Object.values(this.allScans);
    },

    itemList: function() {
      // Get list of current items to show
      // If galleryFolder (ie inside a scan folder), show scan captures
      // Otherwise, show root captures and scan cards
      if (this.galleryFolder) {
        console.log(this.allScans[this.galleryFolder].captures);
        return this.allScans[this.galleryFolder].captures;
      } else {
        return this.noScanCaptures.concat(this.scanList);
      }
    },

    filteredItems: function() {
      // Filter itemList by checkedTags
      return this.filterCaptures(this.itemList, this.checkedTags);
    },

    filteredCaptures: function() {
      var captures = {};

      for (var item of this.filteredItems) {
        // If it's a dataset
        if ("captures" in item) {
          for (var capture of item.captures) {
            // Get the ID of each capture in the set
            captures[capture.metadata.image.id] = capture;
          }
        } else {
          // If it's a single capture, get the ID of the capture
          captures[item.metadata.image.id] = item;
        }
      }

      return captures;
    },

    sortedItems: function() {
      // Sort filteredItems using sortCaptures function
      return this.sortCaptures(this.filteredItems);
    }
  },

  mounted() {
    // Update on mount (does nothing if not connected)
    this.updateCaptures();
    // A global signal listener to perform a gallery refresh
    this.$root.$on("globalUpdateCaptures", () => {
      this.updateCaptures();
    });
    // A global signal listener to set the gallery folder
    this.$root.$on("globalUpdateCaptureFolder", folder => {
      this.galleryFolder = folder;
    });
  },

  created: function() {
    // Watch for host 'ready', then update status
    this.unwatchStoreFunction = this.$store.watch(
      (state, getters) => {
        return getters.ready;
      },
      ready => {
        if (ready) {
          // If the connection is now ready, update capture list
          this.updateCaptures();
        } else {
          // If the connection is now disconnected, empty capture list
          this.captures = {};
        }
      }
    );
  },

  beforeDestroy() {
    // Remove global signal listener to perform a gallery refresh
    this.$root.$off("globalUpdateCaptures");
    // Remove global signal listener to set the gallery folder
    this.$root.$off("globalUpdateCaptureFolder");
    // Then we call that function here to unwatch
    if (this.unwatchStoreFunction) {
      this.unwatchStoreFunction();
      this.unwatchStoreFunction = null;
    }
  },

  methods: {
    updateCaptures: function() {
      if (this.$store.state.available) {
        console.log("Updating capture list...");
        axios
          .get(this.capturesUri)
          .then(response => {
            this.captures = response.data;
          })
          .catch(error => {
            this.modalError(error); // Let mixin handle error
          });
      } else {
        console.log("Delaying capture update until connection is available");
      }
    },

    filterCaptures: function(list, filterTags) {
      // Filter a list of captures by an array of tags
      var result = [];
      for (var capture of list) {
        // Assume exclusion
        var includeCapture = false;

        // Filter by selected tags
        var tags = capture.metadata.image.tags;
        let checker = (arr, target) => target.every(v => arr.includes(v));
        // True if all tags match
        includeCapture = checker(tags, filterTags);

        // Add to capture list if matched
        if (includeCapture == true) {
          result.push(capture);
        }
      }

      return result;
    },

    sortCaptures: function(list) {
      // Sort a list of captures by metadata time
      function compare(a, b) {
        if (a.metadata.image.acquisitionDate < b.metadata.image.acquisitionDate)
          return -1;
        if (a.metadata.image.acquisitionDate > b.metadata.image.acquisitionDate)
          return 1;
        return 0;
      }

      if (this.sortDescending == true) {
        return list.sort(compare).reverse();
      } else {
        return list.sort(compare);
      }
    }
  }
};
</script>

<style scoped lang="less">
.gallery-navbar {
  border-width: 0 0 1px 0;
  border-style: solid;
  border-color: rgba(180, 180, 180, 0.25);
}
.gallery-navbar,
.gallery-folder-heading {
  margin-bottom: 30px;
}
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, 320px);
  justify-content: center;
}
.gallery-grid > div {
  display: inline-block;
  margin-bottom: 20px;
}

/deep/ .capture-card {
  width: 300px;
  height: 100%; // Used to have all cards in a row match their heights
  margin-left: auto;
  margin-right: auto;
}
</style>
