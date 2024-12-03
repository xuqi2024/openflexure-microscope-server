<template>
  <!-- Grid managing tab content -->
  <div class="uk-height-1-1 view-component">
    <div class="uk-padding-small">
      <statusPane class="uk-width-large" />
    </div>
    <div class="uk-padding-small">
      <h2>Links</h2>
      <a
        class="uk-link"
        target="_blank"
        href="https://gitlab.com/openflexure/openflexure-microscope-server/-/issues"
      >
        Report an issue
      </a>
    </div>
    <div class="uk-padding-small">
      <h2>Developer tools</h2>
      <devTools class="uk-width-large" />
    </div>
  </div>
</template>

<script>
import devTools from "./aboutComponents/devTools.vue";
import statusPane from "./aboutComponents/statusPane.vue";

export default {
  name: "AboutContent",

  components: {
    devTools,
    statusPane
  }
};
</script>
