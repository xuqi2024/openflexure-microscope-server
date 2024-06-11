<template>
  <div class="uk-padding-small">
    <div v-show="!backendOK" class="uk-alert-danger">
      The stage calibration detect Thing seems to be missing or incompatible.
    </div>
    <div v-show="backendOK">
      <div class="uk-margin">
        <action-button
          thing="range_of_motion"
          action="measure_rom"
          submit-label="Measure range of motion"
          :can-terminate="true"
          :poll-interval="0.1"
          @response="alertROMMeasured"
        />
      </div>
      <div class="uk-margin">
        <action-button
          thing="recentre_stage"
          action="recentre"
          submit-label="Recentre stage"
          :can-terminate="true"
          :poll-interval="0.1"
        />
      </div>
    </div>
  </div>
</template>

<script>
import ActionButton from "../../labThingsComponents/actionButton.vue";

export default {
  name: "paneStage",

  components: {
    ActionButton
  },

  computed: {
    backendOK() {
      return this.thingAvailable("range_of_motion");
    }
  },

  methods: {
    alertROMMeasured() {
      this.modalNotify(`Range of motion has been measured`);
    }
  }
};
</script>
