<template>
  <!-- Grid managing tab content -->
  <div uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <div class="control-component">
      <paneNavigate />
    </div>
    <div class="view-component uk-width-expand">
      <streamDisplay />
    </div>
  </div>
</template>

<script>
import paneNavigate from "../controlComponents/paneNavigate";
import streamDisplay from "../viewComponents/streamDisplay.vue";

export default {
  name: "NavigateContent",

  components: {
    paneNavigate,
    streamDisplay
  }
};
</script>
