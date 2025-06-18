<template>
  <div id="modal-example" ref="calibrationModalEl" uk-modal="bg-close: false;">
    <div v-if="ready" class="uk-modal-dialog uk-modal-body">
      <h2 class="uk-modal-title">Microscope Calibration</h2>
      <div v-show="stepValue == 0">
        <p>
          <b
            >Some important microscope calibration data is currently missing.</b
          >
        </p>
        <p>
          Your microscope will still function, however some functionality will
          be limited, and image quality will likely suffer.
        </p>
        <p>
          <b>Click Next to begin microscope calibration.</b>
        </p>
      </div>

      <div v-show="stepValue == 1">
        <h3>Lens-shading</h3>
        <div v-if="isLSTCalibrated">
          <p>
            <b
              >Your lens-shading table has already been calibrated. Click Next
              to move on.</b
            >
          </p>
        </div>
        <div v-else>
          <p>
            <b
              >Follow the important steps below before starting lens-shading
              calibration!</b
            >
          </p>
          <ul class="uk-list uk-list-bullet">
            <li>Remove any samples from your microscope</li>
            <li>Ensure your illumination is on and properly fixed in place</li>
          </ul>

          <miniStreamDisplay
            v-if="stepValue == 1"
            class="mini-preview"
          ></miniStreamDisplay>

          <p>Once you're ready, click auto-calibrate.</p>

          <cameraCalibrationSettings
            :show-extra-settings="false"
            :camera-uri="cameraUri"
          ></cameraCalibrationSettings>
        </div>
      </div>

      <div v-show="stepValue == 2">
        <h3>Camera-stage mapping</h3>
        <div v-if="isCSMCalibrated">
          <p>
            <b
              >Your camera-stage mapping has already been calibrated. Click Next
              to move on.</b
            >
          </p>
        </div>
        <div v-else-if="!canCSMCalibrated">
          <p>
            <b
              >No stage connected. Please skip this step, or connect a valid
              stage, then reboot your microscope.</b
            >
          </p>
        </div>
        <div v-else>
          <p>
            <b
              >Follow the important steps below before starting camera-stage
              mapping calibration!</b
            >
          </p>
          <ul class="uk-list uk-list-bullet">
            <li>Insert a clearly visible sample to the microscope</li>
            <li>
              Ensure the sample is reasonably well centered on the microscope
              camera
            </li>
          </ul>

          <miniStreamDisplay
            v-if="stepValue == 2"
            class="mini-preview"
          ></miniStreamDisplay>

          <p>Once you're ready, click auto-calibrate.</p>

          <CSMCalibrationSettings
            :show-extra-settings="false"
          ></CSMCalibrationSettings>
        </div>
      </div>

      <div v-show="stepValue == 3">
        <h3>Range of Motion</h3>
          <p>
            <b
              >Follow the important steps below before starting range of motion 
              calibration!</b
            >
          </p>
          <ul class="uk-list uk-list-bullet">
            <li>Insert a clearly visible sample to the microscope</li>
            <li>
              Ensure the sample is reasonably well centered on the microscope
              camera
            </li>
            <li>Ensure the sample is densely featured.</li>
            <li>Ensure the sample is large enough to fully test the range of motion.
              <ul class="uk-list uk-list-bullet">
                <li>If you have printed a standard stage, the sample needs to be at least 12mm in diameter.</li>
                <li>Otherwise, the sample needs to have a diameter of the range of motion you specified.</li>
              </ul>
            </li>
          </ul>

          <miniStreamDisplay
            v-if="stepValue == 3"
            class="mini-preview"
          ></miniStreamDisplay>

          <p>Once you're ready, click auto-calibrate.</p>

          <ROMsettings
            :show-extra-settings="false"
          ></ROMsettings>
        </div>

      <div v-show="stepValue == 4">
        <p>
          <b>Calibration complete</b>
        </p>
        <p>
          Click Finish to return to your microscope, or Restart to re-run the
          calibration routine
        </p>
      </div>

      <p class="uk-text-right">
        <button
          v-show="stepValue == 0"
          class="uk-button uk-button-default uk-modal-close"
          type="button"
        >
          Cancel
        </button>
        <button
          v-show="stepValue == 4"
          class="uk-button uk-button-default"
          type="button"
          @click="stepValue = 0"
        >
          Restart
        </button>
        <button
          v-show="stepValue < 4"
          class="uk-button uk-button-primary uk-margin-left"
          type="button"
          @click="increment()"
        >
          Next
        </button>
        <button
          v-show="stepValue == 4"
          class="uk-button uk-button-primary uk-margin-left"
          type="button"
          @click="hide()"
        >
          Finish
        </button>
      </p>
    </div>
  </div>  
</template>

<script>
import cameraCalibrationSettings from "../tabContentComponents/settingsComponents/cameraSettingsComponents/cameraCalibrationSettings.vue";
import CSMCalibrationSettings from "../tabContentComponents/settingsComponents/CSMSettingsComponents/CSMCalibrationSettings.vue";
import miniStreamDisplay from "../genericComponents/miniStreamDisplay.vue";
import ROMsettings from "../tabContentComponents/stageComponents/paneStage.vue"

export default {
  name: "CalibrationModal",

  components: {
    cameraCalibrationSettings,
    CSMCalibrationSettings,
    miniStreamDisplay,
    ROMsettings
  },

  data: function() {
    return {
      ready: false,
      stepValue: 0,
      isCSMCalibrated: undefined,
      isLSTCalibrated: undefined
    };
  },

  computed: {
    canCSMCalibrated: function() {
      // Assert CSM extension is enabled
      return this.thingAvailable("camera_stage_mapping");
    },
    canLSTCalibrated: function() {
      // Assert LST extension is enabled
      return (
        "calibrate_lens_shading" in this.thingDescription("camera").actions
      );
    },
    isUseful: function() {
      var CSMUseful = this.canCSMCalibrated && !this.isCSMCalibrated;
      var LSTUseful = this.canLSTCalibrated && !this.isLSTCalibrated;
      return CSMUseful || LSTUseful;
    },
    cameraUri: function() {
      return `${this.$store.getters.baseUri}/camera/`;
    }
  },

  mounted() {
    this.$refs["calibrationModalEl"].addEventListener("hidden", this.onHide);
  },

  methods: {
    show: async function() {
      // Check if the camera and stage are calibrated, if they can be
      if (this.canCSMCalibrated) {
        let csm = await this.readThingProperty(
          "camera_stage_mapping",
          "image_to_stage_displacement_matrix",
          true
        );
        this.isCSMCalibrated = Boolean(csm);
      }
      if (this.canLSTCalibrated) {
        this.isLSTCalibrated = await this.readThingProperty(
          "camera",
          "lens_shading_is_static"
        );
      }
      // Check if this calibration wizard can actually do anything useful
      if (this.isUseful) {
        this.ready = true;
        this.stepValue = 0;
        // Show the modal
        var el = this.$refs["calibrationModalEl"];
        this.showModalElement(el); // Calls the mixin
      } else {
        // If not useful, we just return the onClose event immediately
        this.onHide();
      }
    },
    // Forces modal to show on button press
    force_show: function() {
      this.ready = true;
      this.stepValue = 0;
        // Show the modal
        var el = this.$refs["calibrationModalEl"];
        this.showModalElement(el); // Calls the mixin
    },

    hide: function() {
      // Show the modal
      var el = this.$refs["calibrationModalEl"];
      this.hideModalElement(el); // Calls the mixin
      this.ready = false;
    },

    onHide: function() {
      this.$emit("onClose");
    },

    decrement: function() {
      if (this.stepValue > 0) {
        this.stepValue = this.stepValue - 1;
      }
    },

    increment: function() {
      // Upper bound on section number
      if (this.stepValue < 4) {
        this.stepValue = this.stepValue + 1;
        return true;
      }
    }
  }
};
</script>

<style scoped>
.mini-preview {
  width: 75%;
  margin-left: auto;
  margin-right: auto;
}
</style>
