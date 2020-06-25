<template>
  <div>
    <form class="uk-form-stacked" @submit.prevent="overrideAPIHost">
      <label class="uk-form-label">Override API origin</label>
      <input v-model="currentOrigin" class="uk-input" type="text" />
    </form>
  </div>
</template>

<script>
// Export main app
export default {
  name: "DevTools",

  components: {},

  data: function() {
    return {
      currentOrigin: this.$store.state.origin
    };
  },

  methods: {
    overrideAPIHost: function() {
      this.$store.commit("changeOrigin", this.currentOrigin);
    }
  }
};
</script>

<style scoped lang="less">
.error-icon {
  font-size: 120px;
}
</style>
