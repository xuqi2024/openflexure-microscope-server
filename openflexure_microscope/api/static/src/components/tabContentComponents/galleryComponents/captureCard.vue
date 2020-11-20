<template>
  <div
    class="capture-card uk-card uk-card-default uk-padding-remove uk-width-medium"
    :class="{ 'uk-card-secondary': $store.state.globalSettings.darkMode }"
  >
    <div class="uk-card-media-top">
      <a class="lightbox-link" :href="imgURL" :data-caption="name">
        <img
          class="uk-width-1-1"
          :data-src="thumbURL"
          :alt="id"
          width="300"
          height="225"
          uk-img
        />
      </a>
    </div>

    <div class="uk-card-body uk-padding-small">
      <div
        class="uk-width-1-1 uk-margin-small uk-margin-remove-left uk-margin-remove-right"
        uk-grid
      >
        <div class="uk-margin-remove-top uk-padding-remove uk-width-expand">
          {{ name }}
        </div>
        <div class="uk-margin-remove-top uk-padding-remove uk-width-auto">
          <a href="#" class="uk-icon" @click="delCaptureConfirm()">
            <i class="material-icons">delete</i>
          </a>
        </div>
      </div>

      <div
        class="uk-text-meta uk-margin-remove-top uk-padding-remove uk-width-expand"
      >
        <time>{{ time }}</time>
      </div>
      <div
        class="uk-text-meta uk-margin-remove-top uk-padding-remove uk-width-auto"
      >
        <a :href="metadataModalTarget" uk-toggle>More...</a>
      </div>
    </div>

    <div class="uk-card-footer uk-padding-small">
      <div v-for="tag in tags" :key="tag" class="uk-display-inline">
        <span
          v-if="tag === 'temporary'"
          class="uk-label uk-label-danger uk-margin-small-right"
          uk-tooltip="title: Capture will be removed automatically; delay: 500"
          >Temporary</span
        >
        <span
          v-else
          class="uk-label uk-margin-small-right deletable-label"
          @click="delTagConfirm(tag)"
        >
          {{ tag }}
        </span>
      </div>

      <a :href="tagModalTarget" uk-toggle>
        <span class="uk-label uk-label-success uk-margin-small-right">Add</span>
      </a>
    </div>

    <!-- Metadata modal -->
    <div :id="metadataModalID" uk-modal>
      <div
        class="uk-modal-dialog uk-modal-body"
        :class="{
          'uk-light uk-background-secondary':
            $store.state.globalSettings.darkMode
        }"
      >
        <button class="uk-modal-close-default" type="button" uk-close></button>
        <h2 class="uk-modal-title">{{ name }}</h2>
        <p><b>Path: </b>{{ path }}</p>
        <p><b>Time: </b>{{ time }}</p>
        <p><b>ID: </b>{{ id }}</p>
        <p><b>Format: </b>{{ format }}</p>

        <hr />

        <div v-for="(value, key) in annotations" :key="key">
          <p>
            <b>{{ key }}: </b>{{ value }}
          </p>
        </div>

        <hr />

        <div class="uk-flex-bottom" uk-grid>
          <div class="uk-width-2-3">
            <keyvalList v-model="newAnnotations" />
          </div>
          <div class="uk-width-1-3">
            <button
              class="uk-button uk-button-primary uk-form-small uk-width-1-1"
              @click="handleAnnotationsSubmit()"
            >
              Add annotation
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- New tag modal -->
    <div :id="tagModalID" uk-modal>
      <form
        class="uk-modal-dialog uk-modal-body uk-margin-auto-vertical"
        :class="{
          'uk-light uk-background-secondary':
            $store.state.globalSettings.darkMode
        }"
        @submit.prevent="handleTagSubmit"
      >
        <div class="uk-inline">
          <span class="uk-form-icon"><i class="material-icons">label</i></span>
          <input
            v-model="newTag"
            autofocus
            class="uk-input uk-form-width-medium uk-form-small"
            type="text"
            name="tagname"
            placeholder="tag"
          />

          <button
            class="uk-button uk-button-default uk-margin-left uk-form-small uk-modal-close"
            type="button"
          >
            Cancel
          </button>
          <button
            type="submit"
            class="uk-button uk-button-primary uk-margin-left uk-form-small"
          >
            Save
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import UIkit from "uikit";
import axios from "axios";

import keyvalList from "../../fieldComponents/keyvalList";

// Export main app
export default {
  name: "CaptureCard",

  components: {
    keyvalList
  },

  props: {
    id: {
      type: String,
      required: true
    },
    name: {
      type: String,
      required: true
    },
    time: {
      type: String,
      required: true
    },
    path: {
      type: String,
      required: true
    },
    format: {
      type: String,
      required: true
    },
    links: {
      type: Object,
      required: true
    },
    tags: {
      type: Array,
      required: false,
      default: function() {
        return [];
      }
    },
    annotations: {
      type: Object,
      required: false,
      default: function() {
        return {};
      }
    }
  },

  data: function() {
    return {
      newTag: "",
      newAnnotations: {}
    };
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
    thumbURL: function() {
      return `${this.links.download.href}?thumbnail=true`;
    },
    imgURL: function() {
      return this.links.download.href;
    },
    tagsURL: function() {
      return this.links.tags.href;
    },
    annotationsURL: function() {
      return this.links.annotations.href;
    },
    captureURL: function() {
      return this.links.self.href;
    }
  },

  methods: {
    getMetadata: function() {
      // Send metadata request
      console.log("Loading capture metadata...");
      axios
        .get(this.captureURL)
        .then(response => {
          this.$emit("update:tags", response.data.metadata.image.tags);
          this.$emit(
            "update:annotations",
            response.data.metadata.image.annotations
          );
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },
    handleTagSubmit: function(event) {
      if (this.newTag !== "") {
        this.newTagRequest(this.newTag);
        this.newTag = "";
      }
      UIkit.modal(event.target.parentNode).hide();
    },

    handleAnnotationsSubmit: function() {
      this.putAnnotationsRequest(this.newAnnotations);
      this.newAnnotations = {};
    },

    delCaptureConfirm: function() {
      this.modalConfirm("Permanantly delete capture?").then(() => {
        this.delCaptureRequest();
      });
    },

    delCaptureRequest: function() {
      // Send tag DELETE request
      axios
        .delete(this.captureURL)
        .then(() => {
          // Emit signal to update capture list
          this.$root.$emit("globalUpdateCaptures");
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    newTagRequest: function(tagString) {
      // Send tag PUT request
      axios
        .put(this.tagsURL, [tagString])
        .then(() => {
          // Update tag array
          this.getTagRequest();
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    putAnnotationsRequest: function(annotationsObject) {
      // Send metadata PUT request
      axios
        .put(this.annotationsURL, annotationsObject)
        .then(() => {
          // Update metadata object
          this.getAnnotationsRequest();
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    delTagConfirm: function(tagString) {
      this.modalConfirm(`Remove tag '${tagString}'?`).then(() => {
        this.delTagRequest(tagString);
      });
    },

    delTagRequest: function(tagString) {
      console.log(tagString);
      // Send tag DELETE request
      axios
        .delete(this.tagsURL, { data: [tagString] })
        .then(() => {
          // Update tag array
          this.getTagRequest();
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    getTagRequest: function() {
      // Send tag request
      axios
        .get(this.tagsURL)
        .then(response => {
          // Pass the update tag array to the parent
          this.$emit("update:tags", response.data);
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    getAnnotationsRequest: function() {
      // Send tag request
      axios
        .get(this.annotationsURL)
        .then(response => {
          // Pass the update annotation array to the parent
          this.$emit("update:annotations", response.data);
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    makeModalName: function(prefix) {
      return prefix + this.id;
    }
  }
};
</script>
