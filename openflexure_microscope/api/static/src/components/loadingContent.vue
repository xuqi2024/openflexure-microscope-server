<template>
  <div class="uk-flex uk-flex-column uk-flex-center uk-height-1-1">
    <div
      v-if="$store.state.waiting"
      class="uk-align-center"
      uk-spinner="ratio: 3"
    />
    <div v-if="$store.state.waiting" class="uk-align-center">Loading...</div>
    <i class="material-icons uk-align-center error-icon">error_outline</i>
    <div v-if="$store.state.error" class="uk-align-center">
      {{ $store.state.error }}
    </div>
    <div class="uk-align-center">
      <devTools class="uk-width-medium" />
    </div>
  </div>
</template>

<script>
import devTools from "./tabContentComponents/aboutComponents/devTools.vue";

// Export main app
export default {
  name: "LoadingContent",

  components: { devTools },

  data: function () {
    return {};
  },
};
</script>

<style scoped lang="less">
.error-icon {
  font-size: 120px;
}
</style>
