<template>
  <div
    id="CSMSettings"
    class="uk-grid uk-grid-divider uk-child-width-expand"
    uk-grid
  >
    <div class="uk-width-large">
      <h3>Camera/stage mapping</h3>
      <p>
        Camera/stage mapping allows the stage to move relative to the camera
        view. This enables functions like click-to-move, and more precise tile
        scans.
      </p>
      <CSMCalibrationSettings />
    </div>
    <div id="mini-stream">
      <miniStreamDisplay />
    </div>
  </div>
</template>

<script>
import CSMCalibrationSettings from "./CSMSettingsComponents/CSMCalibrationSettings.vue";
import miniStreamDisplay from "../../genericComponents/miniStreamDisplay.vue";

// Export main app
export default {
  name: "CSMSettings",

  components: {
    CSMCalibrationSettings,
    miniStreamDisplay
  }
};
</script>

<style lang="less">
.center-spinner {
  margin-left: auto;
  margin-right: auto;
}
#mini-stream {
  min-width: 300px;
  max-width: 600px;
  text-align: center;
  margin-left: auto;
  margin-right: auto;
  margin-top: 50px;
}
</style>
