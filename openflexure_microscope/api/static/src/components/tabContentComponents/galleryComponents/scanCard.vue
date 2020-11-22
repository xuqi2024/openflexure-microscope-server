<template>
  <div
    class="capture-card uk-card uk-card-primary uk-padding-remove uk-width-medium"
  >
    <div class="uk-card-media-top">
      <a href="#">
        <img
          class="uk-width-1-1"
          :data-src="thumbnail"
          :alt="id"
          width="300"
          height="225"
          uk-img
          @click="onClick"
        />
      </a>
    </div>

    <div class="uk-card-body uk-padding-small">
      <div
        class="uk-width-1-1 uk-margin-small uk-margin-remove-left uk-margin-remove-right"
        uk-grid
      >
        <div class="uk-margin-remove-top uk-padding-remove uk-width-expand">
          <b>{{ type }}: </b>
          {{ name }}
        </div>
        <div class="uk-margin-remove-top uk-padding-remove uk-width-auto">
          <a href="#" class="uk-icon" @click="delAllConfirm()">
            <i class="material-icons">delete</i>
          </a>
        </div>
      </div>

      <div
        class="uk-text-meta uk-margin-remove-top uk-padding-remove uk-width-expand"
      >
        <time>{{ time }}</time>
      </div>
    </div>

    <div class="uk-card-footer uk-padding-small">
      <span
        v-for="tag in tags"
        :key="tag"
        class="uk-label uk-margin-small-right deletable-label"
      >
        {{ tag }}
      </span>
    </div>
  </div>
</template>

<script>
import axios from "axios";

// Export main app
export default {
  name: "ScanCard",

  props: {
    id: {
      type: String,
      required: true,
    },
    name: {
      type: String,
      required: true,
    },
    time: {
      type: String,
      required: true,
    },
    type: {
      type: String,
      required: false,
      default: "Dataset",
    },
    thumbnail: {
      type: String,
      required: true,
    },
    tags: {
      type: Array,
      required: false,
      default: function () {
        return [];
      },
    },
  },

  computed: {
    allURLs: function () {
      const urls = [];
      for (const capture of this.scanState.captures) {
        urls.push(capture.links.self.href);
      }
      return urls;
    },
  },

  methods: {
    onClick: function () {
      this.$emit("selectFolder", this.id);
    },

    delAllConfirm: function () {
      this.modalConfirm(
        "Permanantly delete all captures in this dataset?"
      ).then(() => {
        this.deleteAll();
      });
    },

    deleteAll: function () {
      axios.all(this.allURLs.map((l) => axios.delete(l))).then(() => {
        // Emit signal to update capture list
        this.$root.$emit("globalUpdateCaptures");
      });
    },
  },
};
</script>
