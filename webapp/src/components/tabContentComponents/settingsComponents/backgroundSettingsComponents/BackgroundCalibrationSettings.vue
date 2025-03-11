<template>
  <div id="BackgroundCalibrationSettings">
    <!--Show auto calibrate if default plugin is enabled-->
    <div v-if="'set_background' in actions" class="uk-margin-small">
      <action-button
        :button-primary="true"
        thing="background_detect"
        action="set_background"
        :submit-label="'Calibrate background appearance'"
        @response="onRecalibrateResponse"
        @error="modalError"
      />
    </div>
</template>

<script>
import ActionButton from "../../../labThingsComponents/actionButton.vue";

// Export main app
export default {
  name: "BackgroundCalibrationSettings",

  components: {
    ActionButton
  },

  computed: {
    actions() {
      return this.$store.getters["wot/thingDescription"]("background_detect")
        .actions;
    },
    properties() {
      return this.$store.getters["wot/thingDescription"]("background_detect")
        .properties;
    }
  },

  methods: {
    onRecalibrateResponse: function() {
      this.modalNotify("Finished background identification.");
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
