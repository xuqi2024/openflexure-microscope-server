<template>
  <!-- Grid managing tab content -->
  <div uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <div class="control-component">
      <vue-friendly-iframe v-if="frame" :src="frame.href"></vue-friendly-iframe>
      <div v-else-if="webComponent">
        <WebComponentLoader
          :component-u-r-l="webComponent.href"
          :component-name="webComponent.name"
        />
      </div>
      <!-- Handle OpenFlexure Forms -->
      <div
        v-for="form in forms"
        v-else-if="forms"
        :key="`${form.route}/${form.name}`.replace(/\s+/g, '-').toLowerCase()"
        class="uk-height-1-1 uk-width-1-1"
      >
        <JsonForm
          :name="form.name"
          :route="form.route"
          :is-task="form.isTask"
          :submit-label="form.submitLabel"
          :schema="form.schema"
          :emit-on-response="form.emitOnResponse"
          v-on="$listeners"
        />
      </div>
    </div>
    <div class="view-component uk-width-expand">
      <galleryDisplay v-if="viewPanel == 'gallery'" />
      <settingsDisplay v-else-if="viewPanel == 'settings'" />
      <streamDisplay v-else />
    </div>
  </div>
</template>

<script>
import JsonForm from "../pluginComponents/JsonForm";
import WebComponentLoader from "../pluginComponents/WebComponentLoader";
import streamDisplay from "../viewComponents/streamDisplay.vue";
import galleryDisplay from "../viewComponents/galleryDisplay.vue";
import settingsDisplay from "../viewComponents/settingsDisplay.vue";

export default {
  name: "ExtensionContent",

  components: {
    JsonForm,
    WebComponentLoader,
    streamDisplay,
    galleryDisplay,
    settingsDisplay
  },

  props: {
    forms: {
      type: Array,
      required: false,
      default: () => []
    },
    webComponent: {
      type: Object,
      required: false,
      default: null
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
