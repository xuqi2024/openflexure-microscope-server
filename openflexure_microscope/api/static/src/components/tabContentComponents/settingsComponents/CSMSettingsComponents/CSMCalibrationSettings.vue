<template>
  <div id="CSMCalibrationSettings">
    <form @submit.prevent="applyConfigRequest">
      <!--Show auto calibrate if default plugin is enabled-->
      <div v-if="'calibrate_xy' in recalibrationLinks" class="uk-margin-small">
        <taskSubmitter
          :button-primary="true"
          :can-terminate="false"
          :requires-confirmation="true"
          :confirmation-message="
            'Start recalibration of the stage to the camera? This may take a while, and the microscope will be locked during this time.'
          "
          :submit-url="recalibrationLinks.calibrate_xy.href"
          :submit-label="'Auto-Calibrate using camera'"
          @response="onRecalibrateResponse"
          @error="onRecalibrateError"
        >
        </taskSubmitter>
      </div>
      <button
        v-if="'get_calibration' in recalibrationLinks"
        v-show="dataAvailable && showExtraSettings"
        type="button"
        class="uk-button uk-button-default uk-width-1-1"
        @click="getCalibrationData()"
      >
        Download calibration data
      </button>
    </form>
  </div>
</template>

<script>
import axios from "axios";
import taskSubmitter from "../../../genericComponents/taskSubmitter";

// Export main app
export default {
  name: "CSMCalibrationSettings",

  components: {
    taskSubmitter
  },

  props: {
    showExtraSettings: {
      type: Boolean,
      required: false,
      default: true
    }
  },

  data: function() {
    return {
      settings: null,
      recalibrationLinks: {},
      isCalibrating: false,
      dataAvailable: false
    };
  },

  computed: {
    settingsUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/instrument/settings`;
    },
    pluginsUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/extensions`;
    }
  },

  mounted() {
    this.updateSettings();
    this.updateRecalibrationLinks();
  },

  methods: {
    updateSettings: function() {
      // Update links
      axios
        .get(this.settingsUri)
        .then(response => {
          this.settings =
            response.data.extensions["org.openflexure.camera_stage_mapping"];
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
          this.settings = {};
        });
    },

    updateCalibrationDataAvailability: function() {
      if ("get_calibration" in this.recalibrationLinks) {
        axios
          .get(this.recalibrationLinks.get_calibration.href)
          .then(response => {
            console.log("CSM data:");
            console.log(response.data);
            if (Object.keys(response.data).length === 0) {
              this.dataAvailable = false;
            } else {
              this.dataAvailable = true;
            }
          })
          .catch(error => {
            this.modalError(error); // Let mixin handle error
          });
      }
    },

    getCalibrationData: function() {
      axios
        .get(this.recalibrationLinks.get_calibration.href)
        .then(response => {
          if (response.data != {}) {
            const data = JSON.stringify(response.data);
            const url = window.URL.createObjectURL(new Blob([data]));
            const link = document.createElement("a");
            link.href = url;
            link.setAttribute("download", "csm_calibration.json");
            document.body.appendChild(link);
            link.click();
          }
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    updateRecalibrationLinks: function() {
      axios
        .get(this.pluginsUri) // Get a list of plugins
        .then(response => {
          const plugins = response.data;
          const foundExtension = plugins.find(
            e => e.title === "org.openflexure.camera_stage_mapping"
          );
          // if camera-stage mapping extension is enabled
          if (foundExtension) {
            // Get plugin action link
            this.recalibrationLinks = foundExtension.links;
            // Update whether calibration data is available
            this.updateCalibrationDataAvailability();
          } else {
            this.recalibrationLinks = {};
          }
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    onRecalibrateResponse: function() {
      this.modalNotify("Finished stage-to-camera calibration.");
      // Update local settings
      this.updateSettings();
    },

    onRecalibrateError: function(error) {
      this.modalError(error); // Let mixin handle error
    }
  }
};
</script>

<style lang="less">
.center-spinner {
  margin-left: auto;
  margin-right: auto;
}
</style>
