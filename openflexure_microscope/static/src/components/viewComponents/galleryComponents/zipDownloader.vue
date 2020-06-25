<template>
  <div v-if="zipBuilderUri" class="uk-width-small">
    <div v-show="downloadReady">
      <button
        :disabled="isDownloading"
        type="button"
        class="uk-button uk-button-default uk-form-small uk-width-1-1"
        @click="downloadWithAxios()"
      >
        {{ isDownloading ? `${downloadProgress}%` : "Download" }}
      </button>
    </div>
    <div v-show="!downloadReady">
      <taskSubmitter
        v-if="zipBuilderUri"
        :can-terminate="false"
        :submit-url="zipBuilderUri"
        :submit-label="'Create ZIP'"
        :submit-data="captureIds"
        @submit="onSubmit"
        @response="onResponse"
        @error="onError"
      >
      </taskSubmitter>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import taskSubmitter from "../../genericComponents/taskSubmitter";

// Export main app
export default {
  name: "ZipDownloader",

  components: {
    taskSubmitter
  },

  props: {
    captureIds: {
      type: Array,
      required: true
    }
  },

  data: function() {
    return {
      downloadProgress: 0,
      isDownloading: false,
      downloadReady: false,
      downloadUrl: null,
      zipBuilderUri: null,
      zipGetterUri: null,
      lastSessionId: null
    };
  },

  computed: {
    pluginsUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/extensions`;
    }
  },

  mounted: function() {
    this.updateZipperUri();
  },

  created: function() {
    // Watch for host 'ready', then update status
    this.unwatchStoreFunction = this.$store.watch(
      (state, getters) => {
        return getters.ready;
      },
      ready => {
        if (ready) {
          // If the connection is now ready, update zipper URL
          this.updateZipperUri();
        }
      }
    );
  },

  methods: {
    updateZipperUri: function() {
      if (this.$store.state.available) {
        axios
          .get(this.pluginsUri) // Get a list of plugins
          .then(response => {
            var plugins = response.data;
            var foundExtension = plugins.find(
              e => e.title === "org.openflexure.zipbuilder"
            );
            // if ZipBuilderPlugin is enabled
            if (foundExtension) {
              // Get plugin action links
              this.zipBuilderUri = foundExtension.links.build.href;
              this.zipGetterUri = foundExtension.links.get.href;
            }
          })
          .catch(error => {
            this.modalError(error); // Let mixin handle error
          });
      } else {
        this.zipBuilderUri = null;
        this.zipGetterUri = null;
      }
    },

    resetZipper: function() {
      this.downloadReady = false;
    },

    forceFileDownload(response) {
      // Start file download by creating and clicking an invisible link
      // One day I hope for a better solution to exist for this...
      // A man can dream.....
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `${this.lastSessionId}.zip`); //or any other extension
      document.body.appendChild(link);
      link.click();
    },

    downloadWithAxios() {
      // Configure progress indicator and response type
      let config = {
        responseType: "blob",
        onDownloadProgress: progressEvent => {
          this.downloadProgress = Math.floor(
            (progressEvent.loaded * 100) / progressEvent.total
          );
        }
      };

      // Set downloading flag
      this.isDownloading = true;

      // Start download
      axios
        .get(this.downloadUrl, config)
        .then(response => {
          this.forceFileDownload(response);
          this.deleteLastZip();
          this.resetZipper();
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        })
        .finally(() => {
          this.isDownloading = false;
        });
    },

    deleteLastZip() {
      axios
        .delete(this.downloadUrl)
        .then(response => {
          console.log(response);
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    onResponse: function(response) {
      this.lastSessionId = response.return.id;
      this.downloadUrl = `${this.zipGetterUri}/${this.lastSessionId}`;
      this.downloadReady = true;
    },

    onSubmit: function(submitData) {
      console.log("SUBMITTED");
      console.log(submitData);
    },

    onError: function(error) {
      this.modalError(error); // Let mixin handle error
    }
  }
};
</script>
