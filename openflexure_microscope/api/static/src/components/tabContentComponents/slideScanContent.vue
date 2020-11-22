<template>
  <!-- Grid managing tab content -->
  <div uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <div class="control-component">
      <paneSlideScan />
    </div>
    <div class="view-component uk-width-expand">
      <streamDisplay />
    </div>
  </div>
</template>

<script>
import paneSlideScan from "./slideScanComponents/paneSlideScan";
import streamDisplay from "./streamContent.vue";

export default {
  name: "SlideScanContent",

  components: {
    paneSlideScan,
    streamDisplay,
  },
};
</script>
