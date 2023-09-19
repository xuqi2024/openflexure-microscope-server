<template>
  <div id="paneCapture" class="uk-padding-small">
    <div>
      <label class="uk-form-label" for="form-stacked-text">Filename</label>
      <input
        v-model="filename"
        class="uk-input uk-width-1-1 uk-form-small"
        name="inputFilename"
        placeholder="Leave blank for default"
      />
    </div>

    <p uk-tooltip="title: Capture will be removed automatically; delay: 500">
      <label
        ><input v-model="temporary" class="uk-checkbox" type="checkbox" />
        Temporary</label
      >
    </p>

    <hr />

    <div class="uk-child-width-1-2" uk-grid>
      <p>
        <label
          ><input
            v-model="fullResolution"
            class="uk-checkbox"
            type="checkbox"
          />
          Full resolution</label
        >
      </p>
      <p>
        <label
          ><input v-model="storeBayer" class="uk-checkbox" type="checkbox" />
          Store raw data</label
        >
      </p>
    </div>

    <hr />

    <p>
      <label
        ><input v-model="resizeCapture" class="uk-checkbox" type="checkbox" />
        Resize capture</label
      >
    </p>

    <div class="uk-child-width-1-2" uk-grid>
      <div>
        <input
          v-model="resizeDims[0]"
          :class="resizeClass"
          class="uk-input uk-form-width-medium uk-form-small"
          type="number"
          name="inputResizeW"
        />
      </div>
      <div>
        <input
          v-model="resizeDims[1]"
          :class="resizeClass"
          class="uk-input uk-form-width-medium uk-form-small"
          type="number"
          name="inputResizeH"
        />
      </div>
    </div>

    <ul uk-accordion="multiple: true">
      <li>
        <a class="uk-accordion-title" href="#">Notes</a>
        <div class="uk-accordion-content">
          <div class="uk-margin-small">
            <textarea
              v-model="captureNotes"
              class="uk-textarea"
              rows="5"
              placeholder="Capture notes"
            ></textarea>
          </div>
        </div>
      </li>

      <li>
        <a class="uk-accordion-title" href="#">Annotations</a>
        <div class="uk-accordion-content">
          <keyvalList v-model="annotations" />
        </div>
      </li>

      <li>
        <a class="uk-accordion-title" href="#">Tags</a>
        <div class="uk-accordion-content">
          <tagList v-model="tags" />
        </div>
      </li>
    </ul>

    <hr />

    <ul uk-accordion="multiple: true">
      <!--Show stack and scan if scan plugin is enabled-->
      <li v-if="scanUri" :class="{ 'uk-open': scanCapture }">
        <a class="uk-accordion-title" href="#">Stack and Scan</a>
        <div class="uk-accordion-content">
          <div class="uk-margin">
            <label
              ><input
                v-model="scanCapture"
                class="uk-checkbox"
                type="checkbox"
              />
              Scan capture</label
            >
          </div>

          <div class="uk-margin-small uk-margin-remove-bottom">
              <label class="uk-form-label" for="form-stacked-text"
                >xy Movement units</label
              >
              <select v-model="xyUnits" class="uk-select">
                <option>Motor steps</option>
                <option>Pixels</option>
                <option>FOV percent</option>
              </select>
            </div>

          <div :class="{ 'uk-disabled': !scanCapture }">
            <div class="uk-grid-small uk-child-width-1-3" uk-grid>
              <div>
                <label class="uk-form-label" for="form-stacked-text"
                  >x step-size</label
                >
                <div class="uk-form-controls">
                  <input
                    v-model="scanStepSize.x"
                    class="uk-input uk-form-small"
                    type="number"
                    name="inputPositionX"
                  />
                </div>
              </div>

              <div>
                <label class="uk-form-label" for="form-stacked-text"
                  >y step-size</label
                >
                <div class="uk-form-controls">
                  <input
                    v-model="scanStepSize.y"
                    class="uk-input uk-form-small"
                    type="number"
                    name="inputPositionY"
                  />
                </div>
              </div>

              <div>
                <label class="uk-form-label" for="form-stacked-text"
                  >z step-size</label
                >
                <div class="uk-form-controls">
                  <input
                    v-model="scanStepSize.z"
                    class="uk-input uk-form-small"
                    type="number"
                    name="inputPositionZ"
                  />
                </div>
              </div>
            </div>

            <div class="uk-grid-small uk-child-width-1-3" uk-grid>
              <div>
                <label class="uk-form-label" for="form-stacked-text"
                  >x steps</label
                >
                <div class="uk-form-controls">
                  <input
                    v-model="scanSteps.x"
                    class="uk-input uk-form-small"
                    type="number"
                    name="inputPositionX"
                    min="1"
                  />
                </div>
              </div>

              <div>
                <label class="uk-form-label" for="form-stacked-text"
                  >y steps</label
                >
                <div class="uk-form-controls">
                  <input
                    v-model="scanSteps.y"
                    class="uk-input uk-form-small"
                    type="number"
                    name="inputPositionY"
                    min="1"
                  />
                </div>
              </div>

              <div>
                <label class="uk-form-label" for="form-stacked-text"
                  >z steps</label
                >
                <div class="uk-form-controls">
                  <input
                    v-model="scanSteps.z"
                    class="uk-input uk-form-small"
                    type="number"
                    name="inputPositionZ"
                    min="1"
                  />
                </div>
              </div>
            </div>

            <div class="uk-margin-small uk-margin-remove-bottom">
              <label class="uk-form-label" for="form-stacked-text"
                >Autofocus</label
              >
              <select v-model="scanDeltaZ" class="uk-select">
                <option>Off</option>
                <option>Coarse</option>
                <option>Medium</option>
                <option>Fine</option>
                <option>Fast</option>
              </select>
            </div>

            <div class="uk-margin-small uk-margin-remove-bottom" v-if="backgroundDetectUri">
              <label class="uk-form-label" for="form-stacked-text">
                <input
                  v-model="detectEmptyFieldsAndSkipAutofocus"
                  class="uk-checkbox"
                  type="checkbox"
                />
                Skip autofocus for empty fields of view
              </label>
            </div>

            <div class="uk-margin-small uk-margin-remove-bottom">
              <label class="uk-form-label" for="form-stacked-text"
                >Scan Style</label
              >
              <select v-model="scanStyle" class="uk-select">
                <option>Raster</option>
                <option>Snake</option>
                <option>Spiral</option>
              </select>
            </div>

            <div class="uk-margin-small uk-margin-remove-bottom">
              <label class="uk-form-label" for="form-stacked-text"
                >Naming style</label
              >
              <select v-model="namingStyle" class="uk-select">
                <option>Coordinates</option>
                <option>Number</option>
              </select>
            </div>
          </div>
        </div>
      </li>
      <!--Show stack and scan if scan plugin is enabled-->
      <li v-if="smartScanUri" :class="{ 'uk-open': smartStack && scanCapture }">
        <a class="uk-accordion-title" href="#">Smart Stack</a>
        <div
          class="uk-accordion-content"
          :class="{ 'uk-disabled': !scanCapture }"
        >
          <div class="uk-margin">
            <label
              ><input
                v-model="smartStack"
                class="uk-checkbox"
                type="checkbox"
              />
              Enable smart stacking</label
            >
          </div>
          <p>
            Smart stacking is an experimental closed-loop Z stack, that checks
            the Z stack is centred on the focus. It requires Z stacking to be
            enabled above (we recommend 9 images in Z) and you must select
            "fast" autofocus.
          </p>
          <div :class="{ 'uk-disabled': !smartStack }">
            <div class="uk-margin-small uk-margin-remove-bottom">
              <label class="uk-form-label" for="form-stacked-text"
                >Autofocus range (steps)</label
              >
              <input
                v-model="smartStackAutofocusDz"
                class="uk-input uk-form-small"
                type="number"
                min="1000"
              />
            </div>
            <div class="uk-margin-small uk-margin-remove-bottom">
              <label class="uk-form-label" for="form-stacked-text"
                >Alignment range (steps)</label
              >
              <input
                v-model="smartStackAlignDist"
                class="uk-input uk-form-small"
                type="number"
                min="100"
              />
            </div>
          </div>
        </div>
      </li>
    </ul>

    <div v-if="scanCapture" class="uk-margin uk-margin-remove-top">
      <taskSubmitter
        v-if="smartStack"
        :submit-url="smartScanUri"
        :submit-data="smartScanPayload"
        :submit-label="'Start Smart Scan'"
        :button-primary="true"
        @response="onScanResponse"
        @error="modalError"
      >
      </taskSubmitter>
      <taskSubmitter
        v-if="!smartStack"
        :submit-url="scanUri"
        :submit-data="scanPayload"
        :submit-label="'Start Scan'"
        :button-primary="true"
        @response="onScanResponse"
        @error="modalError"
      >
      </taskSubmitter>
    </div>

    <button
      v-else
      class="uk-button uk-button-primary uk-margin uk-margin-remove-top uk-width-1-1"
      @click="handleCapture()"
    >
      Capture
    </button>
  </div>
</template>

<script>
import axios from "axios";

import tagList from "../../fieldComponents/tagList";
import keyvalList from "../../fieldComponents/keyvalList";
import taskSubmitter from "../../genericComponents/taskSubmitter";
import { syncDataWithLocalStorage } from "../../../syncDataWithLocalStorage";

/**
 * The capture settings that should persist in local storage are these ones
 */
function defaultCaptureSettings() {
  return {
    filename: "",
    temporary: false,
    fullResolution: false,
    storeBayer: false,
    resizeCapture: false,
    captureNotes: "",
    scanDeltaZ: "Fast",
    scanStyle: "Raster",
    namingStyle: "Coordinates",
    xyUnits: "Motor steps",
    scanStepSize: {
      x: 800,
      y: 640,
      z: 50
    },
    scanSteps: {
      x: 3,
      y: 3,
      z: 5
    },
    resizeDims: [640, 480],
    tags: [],
    annotations: {
      Client: "openflexure-microscope-jsclient:builtin"
    },
    detectEmptyFieldsAndSkipAutofocus: false,
    smartStack: false,
    smartStackThreshold: 0.9,
    smartStackPeakWidth: 200,
    smartStackAlignDist: 900,
    smartStackBacklash: 100,
    smartStackFitStyle: "chevy",
    smartStackMAndMIndex: 10,
    smartStackAutofocusDz: 3000
  };
}

// Export main app
export default {
  name: "PaneCapture",

  components: {
    tagList,
    keyvalList,
    taskSubmitter
  },

  data: function() {
    return {
      ...defaultCaptureSettings(),
      scanCapture: false, // Don't remember the "scan" tickbox in local storage.
      scanUri: null,
      smartScanUri: null,
      backgroundDetectUri: null
    };
  },

  computed: {
    resizeClass: function() {
      return {
        "uk-disabled": !this.resizeCapture
      };
    },
    captureActionUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/actions/camera/capture`;
    },
    pluginsUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/extensions`;
    },
    basePayload: function() {
      var payload = {};

      // Filename
      if (this.filename) {
        payload.filename = this.filename;
      }

      // Basic boolean params
      payload.temporary = this.temporary;
      payload.use_video_port = !this.fullResolution;
      payload.bayer = this.storeBayer;

      // Resizing
      if (this.resizeCapture) {
        payload.resize = {
          width: this.resizeDims[0],
          height: this.resizeDims[1]
        };
      }

      // Additional annotations
      payload.annotations = this.annotations;
      payload.tags = this.tags;

      // Attach notes
      if (this.captureNotes) {
        payload.annotations["Notes"] = this.captureNotes;
      }

      return payload;
    },

    scanPayload: function() {
      // Convert AF selector to dz
      var afDeltas = {
        Off: 0,
        Coarse: 100,
        Medium: 30,
        Fine: 10,
        Fast: 2000
      };
      return {
        ...this.basePayload,
        // Scan params
        grid: [this.scanSteps.x, this.scanSteps.y, this.scanSteps.z],
        stride_size: [
          this.scanStepSize.x,
          this.scanStepSize.y,
          this.scanStepSize.z
        ],
        style: this.scanStyle.toLowerCase(),
        namemode: this.namingStyle.toLowerCase(),
        xyunits: this.xyUnits,
        autofocus_dz: afDeltas[this.scanDeltaZ],
        fast_autofocus: this.scanDeltaZ == "Fast",
        detect_empty_fields_and_skip_autofocus: this.detectEmptyFieldsAndSkipAutofocus
      };
    },
    smartScanPayload: function() {
      return {
        ...this.scanPayload,
        threshold: this.smartStackThreshold,
        width: this.smartStackPeakWidth,
        align_dist: this.smartStackAlignDist,
        backlash: this.smartStackBacklash,
        fit_style: this.smartStackFitStyle,
        m_and_m_index: this.smartStackMAndMIndex,
        autofocus_dz: this.smartStackAutofocusDz
      };
    }
  },

  mounted() {
    this.updateScanUri();
    // Load settings if they have been saved, and set up watchers to sync with local storage
    syncDataWithLocalStorage("captureSettings", this, defaultCaptureSettings());

    // A global signal listener to perform a capture action
    this.$root.$on("globalCaptureEvent", () => {
      this.handleCapture();
    });
  },

  methods: {
    handleCapture: function() {
      var payload = this.basePayload;

      // Do capture
      axios
        .post(this.captureActionUri, payload)
        .then(() => {
          // Flash the stream (capture animation)
          this.$root.$emit("globalFlashStream");
          // Update the global capture list
          this.$root.$emit("globalUpdateCaptures");
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    updateScanUri: function() {
      // Update URIs for the various functions in plugins.
      // This will only work if the plugins are present, so
      // checking if the URIs is null will determine which
      // extensions are available.
      axios
        .get(this.pluginsUri) // Get a list of plugins
        .then(response => {
          var plugins = response.data;
          var foundExtension = plugins.find(
            e => e.title === "org.openflexure.scan"
          );
          // if ScanPlugin is enabled
          if (foundExtension) {
            // Get plugin action link
            this.scanUri = foundExtension.links.tile.href;
          }
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });

      axios
        .get(this.pluginsUri) // Get a list of plugins
        .then(response => {
          var plugins = response.data;
          var foundExtension = plugins.find(
            e => e.title === "org.openflexure.smart-stack"
          );
          if (foundExtension) {
            // Get plugin action link
            this.smartScanUri = foundExtension.links.tile.href;
          }
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });

      axios
        .get(this.pluginsUri) // Get a list of plugins
        .then(response => {
          var plugins = response.data;
          var foundExtension = plugins.find(
            e => e.title === "org.openflexure.background-detect"
          );
          if (foundExtension) {
            // Get plugin action link
            this.backgroundDetectUri = foundExtension.links.grab_and_classify_image.href;
          }
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    onScanResponse: function() {
      this.modalNotify("Finished scan.");
      // Emit signal to update capture list
      this.$root.$emit("globalUpdateCaptures");
    }
  }
};
</script>

<style lang="less">
.deletable-label {
  cursor: pointer;
}

.deletable-label:hover {
  background-color: #f0506e;
}
</style>
