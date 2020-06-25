<template>
  <div
    class="capture-card uk-card uk-card-primary uk-padding-remove uk-width-medium"
  >
    <div class="uk-card-media-top">
      <a href="#">
        <img
          class="uk-width-1-1"
          :data-src="thumbnail"
          :alt="metadata.image.id"
          width="300"
          height="225"
          uk-img
          @click="$root.$emit('globalUpdateCaptureFolder', metadata.image.id)"
        />
      </a>
    </div>

    <div class="uk-card-body uk-padding-small">
      <div
        class="uk-width-1-1 uk-margin-small uk-margin-remove-left uk-margin-remove-right"
        uk-grid
      >
        <div class="uk-margin-remove-top uk-padding-remove uk-width-expand">
          <b>{{ metadata.type || "Dataset" }}: </b> {{ metadata.image.name }}
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
        <time>{{ metadata.image.acquisitionDate }}</time>
      </div>
      <div
        class="uk-text-meta uk-margin-remove-top uk-padding-remove uk-width-auto"
      >
        <a :href="metadataModalTarget" uk-toggle>More...</a>
      </div>
    </div>

    <div class="uk-card-footer uk-padding-small">
      <span
        v-for="tag in metadata.image.tags"
        :key="tag"
        class="uk-label uk-margin-small-right deletable-label"
      >
        {{ tag }}
      </span>
    </div>

    <div :id="metadataModalID" uk-modal>
      <div class="uk-modal-dialog uk-modal-body">
        <button class="uk-modal-close-default" type="button" uk-close></button>
        <h2 class="uk-modal-title">{{ metadata.image.name }}</h2>
        <p><b>Time: </b>{{ metadata.image.acquisitionDate }}</p>
        <p><b>ID: </b>{{ metadata.image.id }}</p>

        <hr />

        <div v-for="(value, key) in metadata.image.annotations" :key="key">
          <p>
            <b>{{ key }}: </b>{{ value }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";

// Export main app
export default {
  name: "ScanCard",

  props: {
    metadata: {
      type: Object,
      required: true
    },
    thumbnail: {
      type: String,
      required: true
    },
    captures: {
      type: Array,
      required: true
    }
  },

  computed: {
    tagModalID: function() {
      return this.makeModalName("tag-modal-");
    },
    tagModalTarget: function() {
      return "#" + this.tagModalID;
    },
    metadataModalID: function() {
      return this.makeModalName("metadata-modal-");
    },
    metadataModalTarget: function() {
      return "#" + this.metadataModalID;
    },
    allURLs: function() {
      var urls = [];
      for (var capture of this.captures) {
        urls.push(capture.links.self.href);
      }
      return urls;
    }
  },

  methods: {
    makeModalName: function(prefix) {
      return prefix + this.metadata.image.id;
    },

    delAllConfirm: function() {
      var context = this;
      this.modalConfirm(
        "Permanantly delete all captures in this dataset?"
      ).then(function() {
        context.deleteAll();
      });
    },

    deleteAll: function() {
      axios
        .all(this.allURLs.map(l => axios.delete(l)))
        .then
        //axios.spread(function(...res) {
        // all requests are now complete
        //console.log(res);
        //})
        ()
        .then(() => {
          // Emit signal to update capture list
          this.$root.$emit("globalUpdateCaptures");
        });
    }
  }
};
</script>
