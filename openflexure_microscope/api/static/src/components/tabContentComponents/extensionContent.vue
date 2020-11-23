<template>
  <!-- Grid managing tab content -->
  <div uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <div class="control-component">
      <vue-friendly-iframe v-if="frame" :src="frame.href"></vue-friendly-iframe>
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
          v-bind="$attrs"
        />
      </div>
    </div>
    <div class="view-component uk-width-expand">
      <galleryContent v-if="viewPanel == 'gallery'" />
      <settingsContent v-else-if="viewPanel == 'settings'" />
      <streamDisplay v-else />
    </div>
  </div>
</template>

<script>
import JsonForm from "../pluginComponents/JsonForm";
import streamDisplay from "./streamContent.vue";
import galleryContent from "../tabContentComponents/galleryContent.vue";
import settingsContent from "../tabContentComponents/settingsContent.vue";

export default {
  name: "ExtensionContent",

  components: {
    JsonForm,
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
