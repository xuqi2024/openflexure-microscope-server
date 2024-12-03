<template>
  <div id="stageSettings" class="uk-width-large">
    The microscope stage is a <b>{{ stageType }}</b
    >. There are no settings to adjust here: to set the geometry of your stage
    (i.e. switch between delta and cartesian), you will need to adjust the
    configuration of your microscope, which cannot be done while it is running.
  </div>
</template>

<script>
export default {
  name: "StageSettings",

  components: {},

  data: function() {
    return {};
  },

  computed: {
    stageType: function() {
      return this.thingDescription("stage").title;
    }
  }
};
</script>

<style lang="less"></style>
