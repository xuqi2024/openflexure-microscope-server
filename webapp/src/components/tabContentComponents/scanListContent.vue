<template>
  <div
    v-observe-visibility="visibilityChanged"
    class="galleryDisplay uk-padding uk-padding-remove-top">
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
    <div id="scan-modal" ref="scanModal" style="padding: 10px;" uk-modal>
      <div class="uk-modal-dialog uk-modal-body " v-if="selectedScan" style="padding: 10px; width: 95%; height: 95%;">
        <h2 class="uk-modal-title">
          {{ selectedScan.name }}
          <button class="uk-modal-close uk-float-right" type="button"><span class="material-symbols-outlined">close</span></button>
          <button class="uk-float-right" type="button" @click="goFullscreen">
            <span class="material-symbols-outlined">fullscreen</span>
          </button>
          </h2>
          <div v-if="selectedScanDZIAvailable" id="viewer_container" style="height: 80%;">
          <OpenSeadragonViewer
            id="openseadragon"
            ref="openseadragon"
            :src="selectedScanDZI"
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
        <div v-if="scansEmpty">
          <h2>No scans available</h2>
          <p>
            There are no scans available to show.
          </p>
        </div>
        <div v-for="item in scans" :key="item.id">
          <div class="uk-card">
            <div class="uk-card-body">
              <div class="uk-card-media-top">
                <div
                  class="view-image uk-padding-remove uk-height-1-1"
                >
                  <img
                    id="thumbnail-stitched-image"
                    class="thumbnail-fit"
                    :src="thumbnailPath(item.name)"
                    onerror="this.src='/titleiconpink.svg';"
                    @click="showScan(item)"
                  />
                </div>
              </div>
              <h3 class="uk-card-title" style="text-align: center;">{{ item.name }}</h3>
              <div class="button-container">
                <action-button
                thing="smart_scan"
                action="download_zip"
                submit-label="Download ZIP"
                :can-terminate="false"
                :submit-data="{ scan_name: item.name }"
                :button-primary="true"
                @response="downloadZipFile"
                @error="modalError"
              />
              <button
                class="uk-button uk-button-default uk-width-1-1"
                @click="deleteScan(item.name)"
              >
                Delete
              </button>
              <action-button
                submit-label="Stitch Images"
                thing="smart_scan"
                action="stitch_scan"
                v-if="item.can_stitch | !item.dzi"
                :can-terminate="false"
                :submit-data="{ scan_name: item.name }"
                :button-primary="false"
                :modal-progress="true"
                @error="modalError"
              />
              <button
                v-if="item.dzi" class="uk-button uk-button-default uk-width-1-1"
                @click="showScan(item)"
              >
              Show Stitched Scan
              </button>
              </div>
              <div>
              <ul>
                <li>{{ item.number_of_images }} images</li>
                <li>created: {{ formatDate(item.created) }}</li>
                <li>modified: {{ formatDate(item.modified) }}</li>
              </ul>
                <li v-if="item.number_of_images<3" class="warning-msg">Not enough images to stitch</li>
                <li v-else-if="!item.dzi & item.stitch_available" class="alert-msg">Interactive preview not available</li> 
                <li v-else-if=!item.stitch_available class="alert-msg">High quality stitch not available</li>  
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
    },
    scansEmpty() {
      return this.scans.length == 0;
    },
    selectedScanDZI() {
      if (this.selectedScan && this.dzi!="") {
        return `${this.$store.getters.baseUri}/scans/${this.selectedScan.name}/images/${this.selectedScan.dzi}`;
      } else {
        return null;
      }
    },
    selectedScanDZIAvailable() {
      return this.selectedScan && this.selectedScan.dzi;
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
      return (
        `${this.$store.getters.baseUri}/smart_scan/scans/stitched_thumbnail.jpg?scan_name=` +
        scan_name
      );
    },
    visibilityChanged(isVisible) {
      if (isVisible) {
        this.updateScans();
      }
    },
    goFullscreen() {
      this.$refs.openseadragon.openFullscreen();
    },
    async updateScans() {
      try {
        let scans = await this.readThingProperty("smart_scan", "scans");
        if (!scans | (scans.length == 0)) {
          this.scans = scans;
        }
        scans.forEach(scan => {
          scan.modified = Date.parse(scan.modified);
          scan.created = Date.parse(scan.created);
          scan.can_stitch = !scan.stitch_available && scan.number_of_images > 3;
        });
        scans.sort((a, b) => {
          return b.modified - a.modified;
        });
        this.scans = scans;
      } catch (err) {
        console.error("Failed to refresh scans");
        console.error(err);
        this.scans = [];
      }
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
      if (scan.dzi){
        this.selectedScan = scan;
        UIkit.modal(this.$refs.scanModal).show();
      }
      else {
        this.modalError(`Scan not stitched for viewing in webapp, please download or stitch`)
      }
    },
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
/*
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, 320px);
  justify-content: center;
  overflow-y: hidden;
}

.gallery-grid > div {
  display: inline-block;
  margin-bottom: 20px;
}

#openseadragon {
  width: 100%;
  height: 100%;
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

/deep/ .capture-card {
  width: 300px;
  height: 100%; // Used to have all cards in a row match their heights
  margin-left: auto;
  margin-right: auto;
}*/

ul {
  display: inline-block;
  text-align: center;
  list-style-type:none;
  margin: 5px 0px 10px 0px;
}

.warning-msg {
  color: red;
  text-align: center;
  font-weight: bold;
}

.alert-msg{
  color: orange;
  text-align: center;
  font-weight: bold;
}
</style>