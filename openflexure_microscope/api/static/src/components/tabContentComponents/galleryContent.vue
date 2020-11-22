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
              :class="{
                'uk-light uk-background-secondary': $store.state.darkMode,
              }"
              class="uk-navbar-dropdown"
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
                        :value="tag"
                        checked
                        class="uk-checkbox"
                        type="checkbox"
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
              class="uk-button uk-button-default uk-width-1-1"
              type="button"
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
        <a class="uk-icon uk-margin-remove" href="#" @click="galleryBack()">
          <i class="material-icons">arrow_back</i>
        </a>
        <div class="uk-margin-left">
          <h3 class="uk-margin-remove uk-margin-left">
            <b>SCAN</b>
            {{ allScans[galleryFolder].name }}
          </h3>
        </div>
      </div>

      <!-- Gallery capture cards -->
      <div class="gallery-grid">
        <div v-for="item in pagedItems" :key="item.id">
          <scanCard
            v-if="'isScan' in item"
            :id="item.id"
            :name="item.name"
            :time="item.time"
            :tags="item.tags"
            :type="item.type"
            :thumbnail="item.thumbnail"
            @selectFolder="selectFolder"
          />
          <captureCard
            v-else
            :id="item.id"
            :links="item.links"
            :name="item.name"
            :format="item.format"
            :path="item.path"
            :time="item.time"
            :tags="item.tags"
            :annotations="item.annotations"
            @update:tags="item.tags = $event"
            @update:annotations="item.annotations = $event"
          />
        </div>
      </div>

      <Paginate
        v-model="page"
        :page-count="numberOfPages"
        :page-range="3"
        :margin-pages="1"
        :container-class="'uk-pagination uk-flex-center'"
        :prev-text="'Prev'"
        :next-text="'Next'"
        :page-class="'page-item'"
        :active-class="'uk-active'"
        :disabled-class="'uk-disabled'"
        :click-handler="scrollToTop()"
      />
    </div>
  </div>
</template>

<script>
import axios from "axios";
import Paginate from "vuejs-paginate";

import captureCard from "./galleryComponents/captureCard.vue";
import scanCard from "./galleryComponents/scanCard.vue";
import ZipDownloader from "./galleryComponents/zipDownloader";

// Export main app
export default {
  name: "GalleryDisplay",

  components: {
    captureCard,
    scanCard,
    ZipDownloader,
    Paginate,
  },

  data: function () {
    return {
      captures: [],
      checkedTags: [],
      sortDescending: true,
      galleryFolder: "",
      scanTag: "scan",
      unwatchStoreFunction: null,
      maxitems: 10,
      page: 1,
    };
  },

  computed: {
    capturesUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/captures`;
    },
    allTags: function () {
      // Return an array of unique tags across all captures
      const tags = [];
      for (const capture of this.captures) {
        for (const tag of capture.tags) {
          if (!tags.includes(tag)) {
            tags.push(tag);
          }
        }
      }
      return tags.sort();
    },

    noScanCaptures: function () {
      // List of captures that are not part of a scan
      const captures = [];
      for (const capture of this.captures) {
        // Add to capture list if matched
        if (!capture.dataset) {
          captures.push(capture);
        }
      }

      return captures;
    },

    allScans: function () {
      // List of scans as capture-like objects
      const scans = {};

      for (const capture of this.captures) {
        const dataset = capture.dataset;

        if (dataset) {
          const id = dataset["id"];

          // If this scan ID hasn't been seen before
          if (!(id in scans)) {
            scans[id] = {};
            scans[id].id = id;
            scans[id].name = dataset.name;
            scans[id].type = dataset.type;
            // Use time of first found capture in dataset
            scans[id].time = capture.time;
            scans[id].isScan = true;
            scans[id].captures = [];
            scans[id].tags = [];
          }
          // Add the capture object to the scan
          scans[id].captures.push(capture);

          // Append missing tags
          for (const tag of capture.tags) {
            if (!scans[id].tags.includes(tag)) {
              scans[id].tags.push(tag);
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

    scanList: function () {
      // List of scans, obtained from this.allScans values
      return Object.values(this.allScans);
    },

    itemList: function () {
      // Get list of current items to show
      // If galleryFolder (ie inside a scan folder), show scan captures
      // Otherwise, show root captures and scan cards
      if (this.galleryFolder) {
        return this.allScans[this.galleryFolder].captures;
      } else {
        return this.noScanCaptures.concat(this.scanList);
      }
    },

    filteredItems: function () {
      // Filter itemList by checkedTags
      return this.filterCaptures(this.itemList, this.checkedTags);
    },

    filteredCaptures: function () {
      const captures = {};

      for (const item of this.filteredItems) {
        // If it's a dataset
        if ("captures" in item) {
          for (const capture of item.captures) {
            // Get the ID of each capture in the set
            captures[capture.id] = capture;
          }
        } else {
          // If it's a single capture, get the ID of the capture
          captures[item.id] = item;
        }
      }

      return captures;
    },

    sortedItems: function () {
      // Sort filteredItems using sortCaptures function
      return this.sortCaptures(this.filteredItems);
    },

    pagedItems: function () {
      const startIndex = (this.page - 1) * this.maxitems;
      return this.sortedItems.slice(startIndex, startIndex + this.maxitems);
    },

    numberOfPages: function () {
      return Math.floor(this.sortedItems.length / this.maxitems);
    },
  },

  mounted() {
    // Update on mount (does nothing if not connected)
    this.updateCaptures();
    // A global signal listener to perform a gallery refresh
    this.$root.$on("globalUpdateCaptures", () => {
      this.updateCaptures();
    });
  },

  created: function () {
    // Watch for host 'ready', then update status
    this.unwatchStoreFunction = this.$store.watch(
      (state, getters) => {
        return getters.ready;
      },
      (ready) => {
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
    // Then we call that function here to unwatch
    if (this.unwatchStoreFunction) {
      this.unwatchStoreFunction();
      this.unwatchStoreFunction = null;
    }
  },

  methods: {
    scrollToTop() {
      document.querySelector("#container-left").scrollTop = 0;
    },

    updateCaptures: function () {
      if (this.$store.state.available) {
        console.log("Updating capture list...");
        axios
          .get(this.capturesUri)
          .then((response) => {
            this.captures = response.data;
          })
          .catch((error) => {
            this.modalError(error); // Let mixin handle error
          });
      } else {
        console.log("Delaying capture update until connection is available");
      }
    },

    filterCaptures: function (list, filterTags) {
      // Filter a list of captures by an array of tags
      const result = [];
      for (const capture of list) {
        // Assume exclusion
        let includeCapture = false;

        // Filter by selected tags
        const tags = capture.tags;
        const checker = (arr, target) => target.every((v) => arr.includes(v));
        // True if all tags match
        includeCapture = checker(tags, filterTags);

        // Add to capture list if matched
        if (includeCapture == true) {
          result.push(capture);
        }
      }

      return result;
    },

    sortCaptures: function (list) {
      // Sort a list of captures by metadata time
      function compare(a, b) {
        if (a.time < b.time) return -1;
        if (a.time > b.time) return 1;
        return 0;
      }

      if (this.sortDescending == true) {
        return list.sort(compare).reverse();
      } else {
        return list.sort(compare);
      }
    },

    galleryBack: function () {
      this.galleryFolder = "";
      this.page = 1;
    },

    selectFolder: function (folderID) {
      this.galleryFolder = folderID;
    },
  },
};
</script>

<style lang="less" scoped>
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
  overflow-y: auto;
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
