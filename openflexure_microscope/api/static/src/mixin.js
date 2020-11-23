import UIkit from "uikit";

export default {
  methods: {
    modalConfirm: function(modalText) {
      // Stop GPU preview to show modal
      this.$emitter.emit("globalTogglePreview", false);
      return new Promise((resolve, reject) => {
        UIkit.modal
          .confirm(modalText, { stack: true })
          .then(
            function() {
              resolve();
            },
            function() {
              reject();
            }
          )
          .finally(function() {
            // Reenable the GPU preview, if it was active before the modal
            if (this.$store.state.autoGpuPreview) {
              this.$emitter.emit("globalTogglePreview", true);
            }
          });
      });
    },

    modalNotify: function(message, status = "success") {
      UIkit.notification({
        message: message,
        status: status
      });
    },

    modalDialog: function(title, message) {
      UIkit.modal.dialog(
        `
        <button class="uk-modal-close-default" type="button" uk-close></button>
        <div class="uk-modal-header">
          <h2 class="uk-modal-title">${title}</h2>
        </div>
        <div class="uk-modal-body">
          <p>${message}</p>
        </div>
      `,
        { stack: true }
      );
    },

    modalError: function(error) {
      var errormsg = this.getErrorMessage(error);
      this.$store.commit("setErrorMessage", errormsg);
      UIkit.notification({
        message: `${errormsg}`,
        status: "danger"
      });
    },

    getErrorMessage: function(error) {
      var errormsg = "";

      // If a response was obtained
      if (error.response) {
        // If the response is a nicely formatted JSON response from the server
        if (error.response.data.message) {
          errormsg = `${error.response.status}: ${error.response.data.message}`;
        }
        // If the response is just some generic error response
        else {
          errormsg = `${error.response.status}: ${error.response.data}`;
        }
        // If the error occured during the request
      } else if (error.request) {
        errormsg = `${error.message}`;
        // Everything else
      } else {
        errormsg = `${error.message}`;
      }
      return errormsg;
    },

    showModalElement: function(element) {
      UIkit.modal(element).show();
    },

    hideModalElement: function(element) {
      UIkit.modal(element).hide();
    },

    toggleModalElement: function(element) {
      UIkit.modal(element).toggle();
    },

    getLocalStorageObj: function(keyName) {
      if (localStorage.getItem(keyName)) {
        try {
          return JSON.parse(localStorage.getItem(keyName));
        } catch (e) {
          localStorage.removeItem(keyName);
          return null;
        }
      }
    },

    setLocalStorageObj: function(keyName, object) {
      const parsed = JSON.stringify(object);
      localStorage.setItem(keyName, parsed);
    }
  }
};
