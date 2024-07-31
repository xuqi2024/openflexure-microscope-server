<template>
  <!-- Grid managing tab content -->
  <div uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <div class="control-component">
      <vue-friendly-iframe v-if="frame" :src="frame.href"></vue-friendly-iframe>
      <!-- OpenFlexure Forms used to be handled here - should now be done another way. -->
    </div>
    <div class="view-component uk-width-expand">
      <galleryContent v-if="viewPanel == 'gallery'" />
      <settingsContent v-else-if="viewPanel == 'settings'" />
      <streamDisplay v-else />
    </div>
  </div>
</template>

<script>
import streamDisplay from "./streamContent.vue";
import galleryContent from "../tabContentComponents/galleryContent.vue";
import settingsContent from "../tabContentComponents/settingsContent.vue";

export default {
  name: "ExtensionContent",

  components: {
    streamDisplay,
    galleryContent,
    settingsContent
  },

  props: {
    forms: {
      type: Array,
      required: false,
      default: () => []
    },
    frame: {
      type: Object,
      required: false,
      default: null
    },
    viewPanel: {
      type: String,
      required: false,
      default: "stream"
    }
  }
};
</script>

<style>
.vue-friendly-iframe {
  height: 100%;
}

.vue-friendly-iframe iframe {
  height: 100%;
}
</style>
