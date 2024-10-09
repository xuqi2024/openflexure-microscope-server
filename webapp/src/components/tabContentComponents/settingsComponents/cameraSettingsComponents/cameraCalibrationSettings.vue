<template>
  <div>
    <!--Show auto calibrate if default plugin is enabled-->
    <div v-if="'full_auto_calibrate' in actions" class="uk-margin-small">
      <action-button
        :can-terminate="false"
        :requires-confirmation="true"
        :confirmation-message="
          'Start recalibration? This may take a while, and the microscope will be locked during this time.'
        "
        thing="camera"
        action="full_auto_calibrate"
        :submit-label="'Full Auto-Calibrate'"
        @response="onRecalibrateResponse"
        @error="modalError"
      />
    </div>
    <div v-if="'auto_expose_from_minimum' in actions" class="uk-margin-small">
      <action-button
        :can-terminate="false"
        :requires-confirmation="false"
        thing="camera"
        action="auto_expose_from_minimum"
        :submit-label="'Auto gain &amp; shutter speed'"
        @response="onRecalibrateResponse"
        @error="modalError"
      />
    </div>
    <div v-if="'calibrate_white_balance' in actions" class="uk-margin-small">
      <action-button
        :can-terminate="false"
        :requires-confirmation="false"
        thing="camera"
        action="calibrate_white_balance"
        :submit-label="'Auto white balance'"
        @response="onRecalibrateResponse"
        @error="modalError"
      />
    </div>
    <div v-if="'calibrate_lens_shading' in actions" class="uk-margin-small">
      <action-button
        :can-terminate="false"
        :requires-confirmation="true"
        :confirmation-message="
          'Is the microscope looking at an evenly illuminated, empty field of view? ' +
            'If not, the current image will show through in any images captured afterwards.'
        "
        thing="camera"
        action="calibrate_lens_shading"
        :submit-label="'Auto flat field correction'"
        @response="onRecalibrateResponse"
        @error="modalError"
      />
    </div>

    <div
      v-show="showExtraSettings"
      v-if="'flatten_lens_shading_table' in actions"
      class="uk-child-width-expand"
    >
      <action-button
        :can-terminate="false"
        :requires-confirmation="false"
        thing="camera"
        action="flat_lens_shading"
        :submit-label="'Disable flat field correction'"
        @response="onRecalibrateResponse"
        @error="modalError"
      />
    </div>
    <div
      v-show="showExtraSettings"
      v-if="'reset_lens_shading' in actions"
      class="uk-child-width-expand"
    >
      <action-button
        :can-terminate="false"
        :requires-confirmation="false"
        thing="camera"
        action="reset_lens_shading"
        :submit-label="'Reset flat field correction'"
        @response="onRecalibrateResponse"
        @error="modalError"
      />
      <div
      v-show="showExtraSettings"
      class="uk-child-width-expand"
      >
      <action-button
        :can-terminate="false"
        :requires-confirmation="false"
        thing="camera"
        action="reset_ccm"
        :submit-label="'Reset ccm'"
        @response="onRecalibrateResponse"
        @error="modalError"
      />
      </div>
    </div>
  </div>
</template>

<script>
import ActionButton from "../../../labThingsComponents/actionButton.vue";

// Export main app
export default {
  name: "CameraCalibrationSettings",

  components: {
    ActionButton
  },

  props: {
    showExtraSettings: {
      type: Boolean,
      required: false,
      default: true
    },
    cameraUri: {
      type: String,
      required: true
    }
  },

  computed: {
    actions() {
      return this.$store.getters["wot/thingDescription"]("camera").actions;
    }
  },

  methods: {
    onRecalibrateResponse: function() {
      this.modalNotify("Finished recalibration.");
    }
  }
};
</script>

<style lang="less"></style>
