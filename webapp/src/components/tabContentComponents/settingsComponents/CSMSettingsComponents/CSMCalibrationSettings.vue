<template>
  <div id="CSMCalibrationSettings">
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

  computed: {
    actions() {
      return this.$store.getters["wot/thingDescription"]("camera_stage_mapping")
        .actions;
    },
    properties() {
      return this.$store.getters["wot/thingDescription"]("camera_stage_mapping")
        .properties;
    }
  },

  methods: {
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

    onRecalibrateResponse: function() {
      this.modalNotify("Finished stage-to-camera calibration.");
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
