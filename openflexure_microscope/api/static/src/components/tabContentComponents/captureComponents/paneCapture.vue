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
            />
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
      <li v-if="scanUri">
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
                    name="inputPositionZx"
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
                    name="inputPositionZx"
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

            <div class="uk-margin-small uk-margin-remove-bottom">
              <label class="uk-form-label" for="form-stacked-text"
                >Scan Style</label
              >
              <select v-model="scanStyle" class="uk-select">
                <option>Raster</option>
                <option>Snake</option>
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
    </ul>

    <div v-if="scanCapture" class="uk-margin uk-margin-remove-top">
      <taskSubmitter
        :submit-url="scanUri"
        :submit-data="scanPayload"
        :submit-label="'Start Scan'"
        :button-primary="true"
        @response="onScanResponse"
        @error="onScanError"
      />
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

// Export main app
export default {
  name: "PaneCapture",

  components: {
    tagList,
    keyvalList,
    taskSubmitter,
  },

  data: function () {
    return {
      filename: "",
      temporary: false,
      fullResolution: false,
      storeBayer: false,
      resizeCapture: false,
      captureNotes: "",
      scanCapture: false,
      scanDeltaZ: "Fast",
      scanStyle: "Raster",
      namingStyle: "Coordinates",
      scanStepSize: {
        x: 800,
        y: 640,
        z: 50,
      },
      scanSteps: {
        x: 3,
        y: 3,
        z: 5,
      },
      resizeDims: [640, 480],
      tags: [],
      annotations: {
        Client: `${process.env.PACKAGE.name}.${process.env.PACKAGE.version}`,
      },
      scanUri: null,
    };
  },

  computed: {
    resizeClass: function () {
      return {
        "uk-disabled": !this.resizeCapture,
      };
    },
    captureActionUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/actions/camera/capture`;
    },
    pluginsUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/extensions`;
    },
    basePayload: function () {
      const payload = {};

      // Filename
      if (this.filename) {
        payload["filename"] = this.filename;
      }

      // Basic boolean params
      payload["temporary"] = this.temporary;
      payload["use_video_port"] = !this.fullResolution;
      payload["bayer"] = this.storeBayer;

      // Resizing
      if (this.resizeCapture) {
        payload["resize"] = {
          width: this.resizeDims[0],
          height: this.resizeDims[1],
        };
      }

      // Additional annotations
      payload["annotations"] = this.annotations;
      payload["tags"] = this.tags;

      // Attach notes
      if (this.captureNotes) {
        payload["annotations"]["Notes"] = this.captureNotes;
      }

      console.log(payload);

      return payload;
    },

    scanPayload: function () {
      const payload = this.basePayload;

      // Scan params
      payload["grid"] = [this.scanSteps.x, this.scanSteps.y, this.scanSteps.z];
      payload["stride_size"] = [
        this.scanStepSize.x,
        this.scanStepSize.y,
        this.scanStepSize.z,
      ];
      payload["style"] = this.scanStyle.toLowerCase();
      payload["namemode"] = this.namingStyle.toLowerCase();

      // Convert AF selector to dz
      const afDeltas = {
        Off: 0,
        Coarse: 100,
        Medium: 30,
        Fine: 10,
        Fast: 2000,
      };

      payload["autofocus_dz"] = afDeltas[this.scanDeltaZ];
      payload["fast_autofocus"] = this.scanDeltaZ == "Fast";

      return payload;
    },
  },

  mounted() {
    this.updateScanUri();
    // A global signal listener to perform a capture action
    this.$root.$on("globalCaptureEvent", () => {
      this.handleCapture();
    });
  },

  methods: {
    handleCapture: function () {
      const payload = this.basePayload;

      // Do capture
      axios
        .post(this.captureActionUri, payload)
        .then(() => {
          // Flash the stream (capture animation)
          this.$root.$emit("globalFlashStream");
          // Update the global capture list
          this.$root.$emit("globalUpdateCaptures");
        })
        .catch((error) => {
          this.modalError(error); // Let mixin handle error
        });
    },

    updateScanUri: function () {
      axios
        .get(this.pluginsUri) // Get a list of plugins
        .then((response) => {
          const plugins = response.data;
          const foundExtension = plugins.find(
            (e) => e.title === "org.openflexure.scan"
          );
          // if ScanPlugin is enabled
          if (foundExtension) {
            // Get plugin action link
            this.scanUri = foundExtension.links.tile.href;
          }
        })
        .catch((error) => {
          this.modalError(error); // Let mixin handle error
        });
    },

    onScanResponse: function (responseData) {
      console.log("Scan finished with response data: ", responseData);
      this.modalNotify("Finished scan.");
    },

    onScanError: function (error) {
      this.modalError(error);
    },
  },
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
