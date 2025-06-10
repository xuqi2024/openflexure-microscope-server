<template>
<div>
  <div id="stageSettings" class="uk-width-large">
    The microscope stage is a <b>{{ stageType }}</b
    >. There are no settings to adjust here: to set the geometry of your stage
    (i.e. switch between delta and cartesian), you will need to adjust the
    configuration of your microscope, which cannot be done while it is running.
  </div>
  <!-- Grid managing tab content -->
  <div uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <div class="control-component">
      <paneStage />
    </div>
        <div class="view-component uk-width-expand">
      <streamDisplay />
    </div>
  </div>
</div>
</template>

<script>
import paneStage from "../stageComponents/paneStage";
import streamDisplay from "../streamContent.vue";

export default {
  name: "StageSettings",

  components: {
    paneStage,
    streamDisplay
  },

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
