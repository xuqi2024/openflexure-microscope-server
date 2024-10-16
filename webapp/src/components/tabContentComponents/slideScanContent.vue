<template>
  <div v-if="!backendOK" class="uk-alert-danger">
    No scan back-end found.
  </div>
  <!-- Grid managing tab content -->
  <div v-else uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <div class="control-component uk-padding-small">
      <div v-show="!scanning" class="uk-padding-small">
        <ul uk-accordion="multiple: true">
          <li>
            <a class="uk-accordion-title" href="#">Configure</a>
            <div class="uk-accordion-content">
              <div class="uk-margin">
                <propertyControl
                  thing-name="smart_scan"
                  property-name="max_range"
                  label="Maximum Distance (steps)"
                />
              </div>
              <div class="uk-margin">
                <propertyControl
                  thing-name="smart_scan"
                  property-name="autofocus_dz"
                  label="Autofocus range (steps)"
                />
              </div>
              <div class="uk-margin">
                <propertyControl
                  thing-name="smart_scan"
                  property-name="stack_dz"
                  label="Stack dz (steps)"
                />
              </div>
              <div class="uk-margin">
                <propertyControl
                  thing-name="smart_scan"
                  property-name="stack_height"
                  label="Images in stack to capture"
                />
              </div>
              <div class="uk-margin">
                <propertyControl
                  thing-name="smart_scan"
                  property-name="stack_test_height"
                  label="Images in stack to test"
                />
              </div>
              <div class="uk-margin">
                <propertyControl
                  thing-name="smart_scan"
                  property-name="overlap"
                  label="Image overlap (0-1)"
                />
              </div>
              <div class="uk-margin">
                <propertyControl
                  thing-name="smart_scan"
                  property-name="max_image_count"
                  label="Max image count (0 for unlimited)"
                />
              </div>
              <div class="uk-margin">
                <propertyControl
                  thing-name="smart_scan"
                  property-name="stitch_tiff"
                  label="When stitching, produce a pyramidal tiff"
                />
              </div>
            </div>
          </li>
          <li class="uk-open">
            <a class="uk-accordion-title" href="#">Scan Settings</a>
            <div class="uk-accordion-content">
              <div class="uk-margin">
                <propertyControl
                  thing-name="smart_scan"
                  property-name="skip_background"
                  label="Detect and skip empty fields"
                />
              </div>
              <div class="uk-margin">
                <propertyControl
                  thing-name="smart_scan"
                  property-name="stitch_automatically"
                  label="Automatically stitch images together"
                />
              </div>
            </div>
          </li>
        </ul>
        <label class="uk-form-label" for="form-stacked-text">Sample ID</label>
        <div class="uk-form-controls">
          <input
            v-model="scan_name"
            class="uk-input uk-form-small"
            type="text"
            name="Scan Name"
          />
        </div>
        <div class="uk-margin">
          <action-button
            ref="smartScanButton"
            thing="smart_scan"
            action="sample_scan"
            :submit-data="{ scan_name: scan_name }"
            submit-label="Start smart scan"
            :can-terminate="true"
            @taskStarted="startScanning"
            @update:taskStatus="taskStatus = $event"
            @update:progress="progress = $event"
            @update:log="log = $event"
          />
        </div>
      </div>
      <div v-show="scanning">
        <h2 v-if="displayImageOnRight">
          Live stitching preview
        </h2>
        <mini-stream-display v-if="displayImageOnRight" />
        <action-log-display
          id="log-display"
          style="margin-top:10px"
          :log="log"
          :task-status="taskStatus"
        />
        <div class="uk-padding-small">
          <action-progress-bar :progress="progress" :task-status="taskStatus" />
          <button
            v-if="cancellable"
            type="button"
            style="margin:auto;"
            class="uk-button uk-button-danger uk-width-1-2"
            @click="$refs.smartScanButton.terminateTask()"
          >
            Cancel
          </button>
          <div
            v-if="!cancellable"
            class="uk-margin uk-grid-small uk-child-width-expand"
            uk-grid
          >
            <button
              type="button"
              class="uk-button"
              @click="
                scanning = false;
                lastStitchedImage = null;
              "
            >
              Close
            </button>
            <action-button
              class="uk-button"
              thing="smart_scan"
              action="create_zip_of_scan"
              submit-label="Download ZIP"
              :can-terminate="false"
              :submit-data="{ scan_name: lastScanName }"
              :button-primary="true"
              @response="downloadZipFile"
              @error="modalError"
            />
          </div>
        </div>
      </div>
      <div class="uk-padding-small">
        <h3 v-if="scanning">Scan ID: {{ lastScanName }}</h3>
      </div>
    </div>
    <div class="view-image uk-width-expand uk-height-1-1">
      <img
        v-if="displayImageOnRight"
        id="last-stitched-image"
        class="image-fit"
        :src="lastStitchedImage"
      />
      <streamDisplay v-else />
    </div>
  </div>
</template>

<script>
import streamDisplay from "./streamContent.vue";
import propertyControl from "../labThingsComponents/propertyControl.vue";
import actionLogDisplay from "../labThingsComponents/actionLogDisplay.vue";
import actionProgressBar from "../labThingsComponents/actionProgressBar.vue";
import MiniStreamDisplay from "../genericComponents/miniStreamDisplay.vue";
import ActionButton from "../labThingsComponents/actionButton.vue";

export default {
  name: "SlideScanContent",

  components: {
    streamDisplay,
    propertyControl,
    actionLogDisplay,
    actionProgressBar,
    MiniStreamDisplay,
    ActionButton
  },

  data() {
    return {
      lastScanName: null,
      scanning: false,
      taskStatus: "pending",
      correlateStatus: "",
      stitchFromStageStatus: "",
      progress: null,
      log: [],
      lastStitchedImage: null,
      scan_name: ""
    };
  },

  computed: {
    backendOK() {
      return this.thingAvailable("smart_scan");
    },
    cancellable() {
      return (this.taskStatus == "running") | (this.taskStatus == "pending");
    },
    displayImageOnRight() {
      return this.scanning & (this.lastStitchedImage !== null);
    }
  },

  methods: {
    onScanError: function(error) {
      this.scanRunning = false;
      this.modalError(error);
    },
    correlateCurrentScan() {},
    startScanning() {
      this.lastStitchedImage = null;
      this.scanning = true;
      setTimeout(this.pollScan, 1000);
    },
    async pollScan() {
      if (this.cancellable) {
        // while the scan is running
        let mtime = await this.readThingProperty(
          "smart_scan",
          "latest_preview_stitch_time"
        );
        if (mtime !== null) {
          this.lastStitchedImage = `${this.$store.getters.baseUri}/smart_scan/latest_preview_stitch.jpg?t=${mtime}`;
        }
        this.lastScanName = await this.readThingProperty(
          "smart_scan",
          "latest_scan_name"
        );
        setTimeout(this.pollScan, 1000); // keep rescheduling until it's stopped
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
    }
  }
};
</script>

<style scoped>
#log-display {
  height: 10em;
}
.control-component {
  width: 33%;
}
</style>
