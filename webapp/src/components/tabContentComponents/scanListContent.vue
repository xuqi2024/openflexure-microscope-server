<template>
  <div
    v-observe-visibility="visibilityChanged"
    class="galleryDisplay uk-padding uk-padding-remove-top"
  >
    <!-- Gallery nav bar -->
    <nav
      class="gallery-navbar uk-navbar-container uk-navbar-transparent"
      uk-navbar="mode: click"
    >
      <!-- Right side buttons -->
      <div class="uk-navbar-right">
        <div class="uk-grid">
          <div>
            <button
              class="uk-button uk-button-default uk-width-1-1"
              style="margin-top:5px;margin-bottom: 2px"
              type="button"
              @click="deleteAllScans()"
            >
              Delete All Scans
            </button>
          </div>
          <div>
            <button
              class="uk-button uk-button-default uk-width-1-1"
              style="margin-top:5px;margin-bottom: 2px"
              type="button"
              @click="updateScans()"
            >
              Refresh Scans
            </button>
          </div>
        </div>
      </div>
    </nav>

    <!-- Modal for scan display -->
    <div id="scan-modal" ref="scanModal" uk-modal>
      <div class="uk-modal-dialog uk-modal-body" v-if="selectedScan">
        <h2 class="uk-modal-title">{{ selectedScan.name }}</h2>
        <action-button
          thing="smart_scan"
          action="create_zip_of_scan"
          submit-label="Download ZIP"
          :can-terminate="false"
          :submit-data="{ scan_name: selectedScan.name }"
          :button-primary="true"
          @response="downloadZipFile"
          @error="modalError"
        />
        <button class="uk-button" @click="deleteScan(selectedScan.name)">
          Delete
        </button>
        <action-button
          submit-label="Stitch Images"
          thing="smart_scan"
          action="stitch_scan"
          :can-terminate="false"
          :submit-data="{ scan_name: selectedScan.name }"
          :button-primary="false"
          :modal-progress="true"
          @error="modalError"
        />
        <ul>
          <li>{{ selectedScan.number_of_images }} images</li>
          <li>created {{ formatDate(selectedScan.created) }}</li>
          <li>modified {{ formatDate(selectedScan.modified) }}</li>
        </ul>
        <div id="viewer_container" class="uk-margin-remove">
          <OpenSeadragonViewer
            src="https://images.openflexure.org/cap_demo/images/PAP.dzi"
            id="openseadragon"
          />
        </div>
      </div>
    </div>

    <!-- Gallery -->
    <div
      v-if="$store.getters.ready"
      class="uk-padding-remove-top"
      uk-lightbox="toggle: .lightbox-link"
    >
      <!-- Gallery capture cards -->
      <div class="gallery-grid uk-grid-match" uk-grid>
        <div v-for="item in scans" :key="item.id">
          <div class="uk-card" @click="showScan(item)">
            <div class="uk-card-body">
            <div class="uk-card-media-top">
              <div class="view-image uk-width-expand uk-padding-remove uk-height-1-1">
                <img
                  id="thumbnail-stitched-image"
                  class="thumbnail-fit"
                  :src=thumbnailPath(item.name)
                  onerror="this.src='/favicon-32x32.png';"
                />
              </div>
              </div>
              <h3 class="uk-card-title">{{ item.name }}</h3>
              <ul>
                <li>{{ item.number_of_images }} images</li>
                <li>created {{ formatDate(item.created) }}</li>
                <li>modified {{ formatDate(item.modified) }}</li>
              </ul>

              <div
                class="uk-text-meta uk-margin-remove-top uk-padding-remove uk-width-expand"
              >
                <time>{{ item.created }}</time>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import UIkit from "uikit";
import actionButton from "../labThingsComponents/actionButton.vue";
import OpenSeadragonViewer from "./scanListComponents/openSeadragonViewer.vue";

// Export main app
export default {
  name: "ScanListContent",
  components: { actionButton, OpenSeadragonViewer },

  data: function() {
    return {
      scans: [],
      selectedScan: null,
      osdViewer: null
    };
  },

  computed: {
    scansUri() {
      return this.$store.getters["wot/thingPropertyUrl"](
        "smart_scan",
        "scans",
        "readproperty",
        true
      );
    }
  },

  async mounted() {
    // Update on mount (does nothing if not connected)
    await this.updateScans();
    // A global signal listener to perform a gallery refresh
    this.$root.$on("globalUpdateScans", () => {
      this.updateScans();
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
          this.updateScans();
        } else {
          // If the connection is now disconnected, empty capture list
          this.captures = {};
        }
      }
    );
  },

  beforeDestroy() {
    // Remove global signal listener to perform a gallery refresh
    this.$root.$off("globalUpdateScans");
    // Then we call that function here to unwatch
    if (this.unwatchStoreFunction) {
      this.unwatchStoreFunction();
      this.unwatchStoreFunction = null;
    }
  },

  methods: {
    thumbnailPath(scan_name) {
      return `${this.$store.getters.baseUri}/smart_scan/scans/stitched_thumbnail.jpg?scan_name=`+scan_name;
    },
    visibilityChanged(isVisible) {
      if (isVisible) {
        this.updateScans();
      }
    },
    async updateScans() {
      let scans = await this.readThingProperty("smart_scan", "scans");
      if (!scans | (scans.length == 0)) {
        this.scans = scans;
      }
      scans.forEach(scan => {
        scan.modified = Date.parse(scan.modified);
        scan.created = Date.parse(scan.created);
      });
      scans.sort((a, b) => {
        return b.modified - a.modified;
      });
      this.scans = scans;
    },
    formatDate(timestamp) {
      let d = new Date(timestamp);
      let yyyy = d.getFullYear();
      let mm = d.getMonth() + 1;
      let dd = d.getDate();
      let HH = d
        .getHours()
        .toString()
        .padStart(2, "0");
      let MM = d
        .getMinutes()
        .toString()
        .padStart(2, "0");
      return `${HH}:${MM} ${dd}/${mm}/${yyyy}`;
    },
    async deleteScan(name) {
      try {
        await this.modalConfirm(`Are you sure you want to delete ${name}?`);
        await axios.delete(`${this.scansUri}/${name}`);
        await this.updateScans();
        this.modalNotify(`Deleted ${name}`);
      } catch (e) {
        // if the confirmation was cancelled, it's rejected with null error
        if (e) this.modalError(e);
      }
    },
    async deleteAllScans() {
      try {
        await this.modalConfirm(
          "Are you sure you want to delete all scans from the microscope? " +
            "This is <b>irreversible</b>!"
        );
        await axios.delete(`${this.scansUri}`);
        await this.updateScans();
        this.modalNotify("Deleted all scans.");
      } catch (e) {
        // if the confirmation was cancelled, it's rejected with null error
        if (e) this.modalError(e);
      }
    },
    async downloadZipFile(response) {
      const scan_name = response.input.scan_name;
      const filename = `${scan_name}_images.zip`;
      const url = response.output.href;
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", filename);
      console.log(link);
      document.body.appendChild(link);
      link.click();
    },
    showScan(scan) {
      this.selectedScan = scan;
      UIkit.modal(this.$refs.scanModal).show();
    }
  }
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
#openseadragon {
  width: 100%;
  height: 400px;
}
#info-panel {
    position: absolute;
    top: 10px;
    left: 10px;
    background-color: rgba(255, 255, 255, 0.7);
    padding: 5px;
    border-radius: 1px;
    z-index: 1000;
}
/*
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
}*/
</style>
