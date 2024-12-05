<template>
  <div id="CSMCalibrationSettings" v-observe-visibility="visibilityChanged">
    <!--Show auto calibrate if default plugin is enabled-->
    <div v-if="'calibrate_xy' in actions" class="uk-margin-small">
      <action-button
        :button-primary="true"
        :can-terminate="true"
        :requires-confirmation="true"
        :confirmation-message="
          'Start recalibration of the stage to the camera? This may take a while, and the microscope will be locked during this time.'
        "
        thing="camera_stage_mapping"
        action="calibrate_xy"
        :submit-label="'Auto-Calibrate using camera'"
        :modal-progress="true"
        @response="onRecalibrateResponse"
        @error="modalError"
      />
    </div>
    <button
      v-if="'last_calibration' in properties"
      v-show="showExtraSettings"
      type="button"
      class="uk-button uk-button-default uk-width-1-1"
      @click="getCalibrationData()"
    >
      Download calibration data
    </button>
    <p v-if="csmMatrixDefined">
      Current CSM matrix: {{ csmMatrix }} at a resolution of
      {{ csmResolution }} <br />
      This means that one motor step is roughly {{ csmRatio }} pixels <br />
      The full field of view is roughly {{ csmFOV }} motor steps
    </p>
  </div>
</template>

<script>
import ActionButton from "../../../labThingsComponents/actionButton.vue";

// Export main app
export default {
  name: "CSMCalibrationSettings",

  components: {
    ActionButton
  },

  props: {
    showExtraSettings: {
      type: Boolean,
      required: false,
      default: true
    }
  },

  data() {
    return {
      csmMatrix: "undefined",
      csmResolution: "undefined",
      csmRatio: "undefined"
    };
  },

  computed: {
    actions() {
      return this.$store.getters["wot/thingDescription"]("camera_stage_mapping")
        .actions;
    },
    properties() {
      return this.$store.getters["wot/thingDescription"]("camera_stage_mapping")
        .properties;
    },
    csmMatrixDefined() {
      return this.csmMatrix != "undefined";
    }
  },

  methods: {
    visibilityChanged(isVisible) {
      if (isVisible) {
        this.updateDisplayedCSM();
      }
    },
    getCalibrationData: async function() {
      try {
        let data = await this.readThingProperty(
          "camera_stage_mapping",
          "last_calibration"
        );
        if (data == {}) {
          throw "No calibration data available.";
        }
        const dataStr = JSON.stringify(data);
        const url = window.URL.createObjectURL(new Blob([dataStr]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", "csm_calibration.json");
        document.body.appendChild(link);
        link.click();
      } catch (error) {
        this.modalError(error); // Let mixin handle error
      }
    },
    updateDisplayedCSM: async function() {
      let csmMatrix = await this.readThingProperty(
        "camera_stage_mapping",
        "image_to_stage_displacement_matrix"
      );
      this.csmResolution = await this.readThingProperty(
        "camera_stage_mapping",
        "image_resolution"
      );
      let streamResolution = await this.readThingProperty(
        "camera",
        "stream_resolution"
      );
      csmMatrix[0][0] = Number(csmMatrix[0][0].toFixed(3));
      csmMatrix[0][1] = Number(csmMatrix[0][1].toFixed(3));
      csmMatrix[1][0] = Number(csmMatrix[1][0].toFixed(3));
      csmMatrix[1][1] = Number(csmMatrix[1][1].toFixed(3));
      this.csmMatrix = csmMatrix;
      this.csmRatio = Number(
        (Math.abs(csmMatrix[1][0]) + Math.abs(csmMatrix[0][1])) / 2
      ).toFixed(3);
      this.csmFOV = [
        Number(
          (
            (streamResolution[0] ** 2 * this.csmRatio) /
            this.csmResolution[1]
          ).toFixed(0)
        ),
        Number(
          (
            (streamResolution[1] ** 2 * this.csmRatio) /
            this.csmResolution[0]
          ).toFixed(0)
        )
      ];
    },
    onRecalibrateResponse: function() {
      this.modalNotify("Finished stage-to-camera calibration.");
      this.updateDisplayedCSM();
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
