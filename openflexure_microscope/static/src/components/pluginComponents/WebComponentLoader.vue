<template>
  <div class="uk-padding-small">
    <div v-if="error" class="uk-padding-small uk-text-danger">
      <b>{{ error }}</b>
    </div>
    <component
      :is="componentName"
      v-if="ready"
      :component-base-u-r-l="ApiRootURL"
    ></component>
  </div>
</template>

<script>
export default {
  name: "WebComponentLoader",

  props: {
    componentURL: {
      type: String,
      required: true
    },
    componentName: {
      type: String,
      required: true
    }
  },

  data: function() {
    return {
      ready: false,
      error: null
    };
  },

  computed: {
    ApiRootURL: function() {
      return `${this.$store.getters.baseUri}/api/v2`;
    }
  },

  mounted() {
    // Method 2
    this.$loadScript(this.componentURL)
      .then(() => {
        const el = customElements.get(this.componentName);
        if (el) {
          this.ready = true;
        } else {
          this.error = `Error: No component ${this.componentName} found.`;
        }
        this.ready = true;
      })
      .catch(() => {
        this.ready = false;
      });
  }
};
</script>

<style scoped></style>
