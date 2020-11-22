<template>
  <!-- Grid managing tab content -->
  <div uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <div class="control-component">
      <paneCapture />
    </div>
    <div class="view-component uk-width-expand">
      <streamDisplay />
    </div>
  </div>
</template>

<script>
import paneCapture from "./captureComponents/paneCapture";
import streamDisplay from "./streamContent.vue";

export default {
  name: "NavigateContent",

  components: {
    paneCapture,
    streamDisplay,
  },
};
</script>
