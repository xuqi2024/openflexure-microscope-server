<template>
  <div
    v-observe-visibility="visibilityChanged"
    class="uk-padding uk-padding-remove-top"
  >
    <!-- Logging nav bar -->
    <nav
      class="logging-navbar uk-navbar-container uk-navbar-transparent"
      uk-navbar="mode: click"
    >
      <!-- Left side controls -->
      <div
        class="uk-navbar-left uk-padding-remove-top uk-padding-remove-bottom"
      ></div>

      <!-- Right side buttons -->
      <div class="uk-navbar-right">
        <div class="uk-grid">
          <div>
            <button
              class="uk-button uk-button-default uk-width-1-1"
              type="button"
              @click="updateLogs()"
            >
              Refresh Logs
            </button>
          </div>
          <div>
            <a class="uk-button uk-button-default" :href="logFileURI" download
              >Download Log File</a
            >
          </div>
        </div>
      </div>
    </nav>

    <!-- Logging items -->
    <div class="uk-width-xlarge uk-align-center">
      <div
        v-for="item in pagedItems"
        :key="item.timestamp"
        uk-alert
        :class="{
          'uk-alert-warning uk-alert': item.data.levelname == 'WARNING',
          'uk-alert-danger uk-alert': item.data.levelname == 'ERROR'
        }"
      >
        <p>
          <b>{{ formatDateTime(item.data.created) }}</b>
        </p>
        {{ item.data.levelname }}: {{ item.data.message }}
      </div>

      <Paginate
        v-model="page"
        :page-count="numberOfPages"
        :page-range="3"
        :margin-pages="1"
        :container-class="'uk-pagination uk-flex-center'"
        :prev-text="'Prev'"
        :next-text="'Next'"
        :page-class="'page-item'"
        :active-class="'uk-active'"
        :disabled-class="'uk-disabled'"
        :click-handler="scrollToTop()"
      >
      </Paginate>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import Paginate from "vuejs-paginate";

export default {
  name: "LoggingContent",

  components: {
    Paginate
  },

  data: function() {
    return {
      maxitems: 20,
      page: 1,
      logs: []
    };
  },

  computed: {
    loggingUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/events/logging`;
    },
    logFileURI: function() {
      return `${this.$store.getters.baseUri}/api/v2/log`;
    },
    pagedItems: function() {
      const startIndex = (this.page - 1) * this.maxitems;
      return this.logs.slice(startIndex, startIndex + this.maxitems);
    },
    numberOfPages: function() {
      return Math.floor(this.logs.length / this.maxitems);
    }
  },

  mounted() {
    // Update on mount (does nothing if not connected)
    this.updateLogs();
  },

  methods: {
    scrollToTop() {
      document.querySelector("#container-left").scrollTop = 0;
    },
    visibilityChanged(isVisible) {
      if (isVisible) {
        this.updateLogs();
      }
    },
    updateLogs: function() {
      console.log("Updating logs...");
      axios
        .get(this.loggingUri)
        .then(response => {
          this.logs = response.data.reverse();
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },
    formatDateTime: function(isoDateTimeString) {
      const date = new Date(isoDateTimeString);
      return date.toLocaleDateString() + " " + date.toLocaleTimeString();
    }
  }
};
</script>

<style lang="less" scoped>
.logging-navbar {
  border-width: 0 0 1px 0;
  border-style: solid;
  border-color: rgba(180, 180, 180, 0.25);
  margin-bottom: 30px;
  height: 80px;
}
</style>
