<template>
  <div>
    <!--Show auto calibrate if default plugin is enabled-->
    <p>MICAT will determine the physical size of a pixel using a USAF Resolution Target</p>
    <div>
      <action-button
          thing=""
          action=""
          submit-label="MICAT"
          :can-terminate="true"
          :requires-confirmation="true"
          :modal-progress="true"
          :confirmation-message="
          'Using the camera and a USAF Resolution Target, the resolution will be measured.'
          "
          :poll-interval="0.1"
        />
    </div>
    <p>Use the slanted edge method with a razor blade to determine the resolution. Position the razor blade at an angle of approximately 9 degrees in the center of the image.</p>
    <div>
        <action-button
          thing=""
          action=""
          submit-label="Razor Blade"
          :can-terminate="true"
          :requires-confirmation="true"
          :modal-progress="true"
          :confirmation-message="
          'Using the camera and a fresh razor blade, the resolution will be measured.'
          "
          :poll-interval="0.1"
        />
    </div>
</div>
</template>

<script>
import ActionButton from "../../../labThingsComponents/actionButton.vue";

export default {
  name: "resolutionCalibrationSettings",

  components: {
    ActionButton
  }
};

</script>