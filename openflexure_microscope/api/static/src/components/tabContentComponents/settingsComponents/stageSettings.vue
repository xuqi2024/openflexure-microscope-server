<template>
  <div id="stageSettings" class="uk-width-large">
    <div>
      <h3>Stage settings</h3>
      <p>
        <label class="uk-form-label">
          Stage geometry
          <div v-if="stageType != 'MissingStage'">
            <form @submit.prevent="setStageType">
              <div class="uk-margin-small">
                <select v-model="stageType" class="uk-select">
                  <option value="SangaStage">SangaStage (Standard)</option>
                  <option value="SangaDeltaStage">SangaStage (Delta)</option>
                </select>
              </div>
              <div>
                <button
                  type="submit"
                  class="uk-button uk-button-primary uk-width-1-1"
                >
                  Change stage geometry
                </button>
              </div>
            </form>
          </div>
          <div v-else class="uk-text-danger"><b>No stage connected</b></div>
        </label>
      </p>
    </div>
  </div>
</template>

<script>
import axios from "axios";

export default {
  name: "StageSettings",

  components: {},

  data: function () {
    return {
      stageType: "MissingStage",
    };
  },

  computed: {
    stageTypeUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/instrument/stage/type`;
    },
  },

  mounted() {
    this.getStageType();
  },

  methods: {
    getStageType: function () {
      console.log("Getting stage type");
      axios
        .get(this.stageTypeUri)
        .then((response) => {
          console.log("Stage type is  " + response.data);
          this.stageType = response.data;
        })
        .catch((error) => {
          this.modalError(error);
        });
    },
    setStageType: function () {
      console.log("Setting stage type");
      axios
        .put(this.stageTypeUri, this.stageType, {
          headers: {
            "Content-Type": "application/json",
          },
        })
        .then((response) => {
          this.stageType = response.data;
          console.log("Stage type set to " + this.stageType);
          this.modalNotify("Stage geometry changed.");
        })
        .catch((error) => {
          this.modalError(error);
        });
    },
  },
};
</script>

<style lang="less"></style>
