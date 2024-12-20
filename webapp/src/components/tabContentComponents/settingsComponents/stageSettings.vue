<template>
  <div id="stageSettings" class="uk-width-large">
    <div>The microscope stage is a <b>{{ stageType }}</b>.</div>
    <div>
      <action-button
        thing="stage"
        action="query"
        :submit-data="{ message: 'SMZ 1' }"
        submit-label="Enable slow Z moves"
        @error="modalError"
      />
    </div>
    
    
  </div>
</template>

<script>
import ActionButton from "../../labThingsComponents/actionButton.vue";

export default {
  name: "StageSettings",

  components: {
    ActionButton
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
