<template>
<div>
  <h3>Resolution</h3>
  <div id="resolutionSettings" class="uk-width-large">
  </div>
  <!-- Grid managing tab content -->
  <div uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <div class="uk-width-large">
      <resolutionCalibrationSettings />
    </div>
        <div class="view-component uk-width-expand">
      <streamDisplay />
    </div>
  </div>
</div>
</template>

<script>
import streamDisplay from "../streamContent.vue";
import resolutionCalibrationSettings from "./resolutionComponents/resolutionCalibrationSettings.vue";

export default {
  name: "resolutionSettings",

  components: {
    resolutionCalibrationSettings,
    streamDisplay
  },
  
};
</script>

<style lang="less"></style>