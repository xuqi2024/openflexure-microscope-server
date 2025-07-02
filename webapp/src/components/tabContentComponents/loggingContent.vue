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
      >
        <select v-model="filterLevel" class="uk-select">
          <option v-for="level in allLevels" :key="level">{{ level }}</option>
        </select>
      </div>

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
          <EndpointButton
            class="uk-button uk-width-1-1"
            :URL="logFileURI"
            buttonLabel="Download Log File"
            :buttonPrimary="false"
            />
          </div>
        </div>
      </div>
    </nav>

    <!-- Logging items -->
    <div class="uk-width-xlarge uk-align-center">
      <div
        v-for="item in pagedItems"
        :key="item.sequence"
        uk-alert
        class="logging-entry"
        :class="{
          'uk-alert-warning uk-alert': item.level == 'WARNING',
          'uk-alert-danger uk-alert': item.level == 'ERROR'
        }"
      >
        <b>{{ formatDateTime(item.timestamp) }}: {{ item.level }}</b>
        <div class="logging-summary">
          {{ item.summary }}
          <a
            v-if="(item.summary != item.message) & !item.expanded"
            style="float: right"
            @click="item.expanded = true"
          >
            More info...
          </a>
          <!-- eslint-disable vue/no-v-html -->
          <div
            v-if="item.expanded"
            class="logging-message"
            v-html="item.message"
          ></div>
          <!-- eslint-enable -->
        </div>
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
import EndpointButton from "../labThingsComponents/endpointButton.vue";

export default {
  name: "LoggingContent",

  components: {
    Paginate,
    EndpointButton
  },

  data: function() {
    return {
      maxitems: 20,
      page: 1,
      logs: [],
      allLevels: ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
      filterLevel: "WARNING"
    };
  },

  computed: {
    filteredLevels: function() {
      let cutoffIndex = this.allLevels.indexOf(this.filterLevel);
      return this.allLevels.slice(cutoffIndex, -1);
    },
    filteredItems: function() {
      var items = [];
      for (var item of this.logs) {
        // Add to capture list if matched
        if (this.filteredLevels.includes(item.level)) {
          items.push(item);
        }
      }

      return items;
    },
    logURI: function() {
      return `${this.$store.getters.baseUri}/log/`;
    },
    logFileURI: function() {
      return `${this.$store.getters.baseUri}/logfile/`;
    },
    pagedItems: function() {
      let startIndex = (this.page - 1) * this.maxitems;
      return this.filteredItems.slice(startIndex, startIndex + this.maxitems);
    },
    numberOfPages: function() {
      return Math.floor(this.filteredItems.length / this.maxitems);
    }
  },

  methods: {
    scrollToTop() {
      const el = document.querySelector("#container-left");
      if (el) {
        el.scrollTop = 0;
      }
    },
    visibilityChanged(isVisible) {
      if (isVisible) {
        this.updateLogs();
      }
    },
    async updateLogs() {
      let response = await axios.get(this.logURI);
      let lines = response.data.split("\n");
      let logs = [];
      let regexp = /^\[(.+?)\] \[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\] (.*)$/;
      for (let line of lines) {
        if (line.length > 0) {
          let m = line.match(regexp);
          if (m) {
            logs.push({
              timestamp: m[1],
              level: m[2],
              summary: m[3],
              message: this.escapeText(m[3]),
              sequence: logs.length,
              expanded: false
            });
          } else if (logs) {
            // If a line does not look like a log entry, append it to the last
            // log entry (i.e. allow multi-line messages)
            let entry = logs[logs.length - 1];
            m = line.match(/^( *)(\^+)/); // detect python stack trace "underlines"
            if (m) {
              let linestart = entry.message.lastIndexOf("\n") + 1;
              let ustart = linestart + m[1].length;
              let uend = ustart + m[2].length;
              entry.message =
                entry.message.substring(0, ustart) +
                "<u>" +
                entry.message.substring(ustart, uend) +
                "</u>" +
                entry.message.substring(uend);
            } else {
              entry.message += "\n" + this.escapeText(line);
              if (entry.message.startsWith("Traceback")) {
                entry.summary = line; // For tracebacks, the last line is the best summary
              }
            }
          } else {
            // if there's no existing log message to append to, discard lines
            // until we find one.
            console.log(
              "Ignored non-matching lines at the start of the log file."
            );
            continue;
          }
        }
      }
      this.logs = logs.reverse(); // Display in reverse chronological order
    },
    formatDateTime: function(isoDateTimeString) {
      isoDateTimeString = isoDateTimeString.replace(",", ".");
      let date = new Date(isoDateTimeString);
      return date.toLocaleDateString() + " " + date.toLocaleTimeString();
    },
    escapeText: function(unsafeText) {
      let div = document.createElement("div");
      div.innerText = unsafeText;
      return div.innerHTML;
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
.logging-entry {
  white-space: break-spaces;
}
.logging-message {
  font-family: monospace;
  overflow-x: auto;
  text-wrap: nowrap;
}
</style>
