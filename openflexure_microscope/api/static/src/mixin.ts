import Vue from 'vue'
import Component from 'vue-class-component'
import UIkit from "uikit";
import {
  AxiosError,
} from "axios";


@Component
export default class GlobalMixin extends Vue {
  modalConfirm(modalText: string) {
    // Stop GPU preview to show modal
    this.$root.$emit("globalTogglePreview", false);

    const showModal = (resolve: () => void, reject: () => void) => {
      UIkit.modal
        .confirm(modalText, { stack: true })
        .then(
          () => {
            resolve();
          },
          () => {
            reject();
          }
        )
        .finally(() => {
          // Reenable the GPU preview, if it was active before the modal
          console.log("Re-enabling GPU preview");
          if (this.$store.state.globalSettings.autoGpuPreview) {
            console.log("Re-enabling preview");
            this.$root.$emit("globalTogglePreview", true);
          }
        });
    };
    return new Promise(showModal);
  }

  modalNotify(message: string, status: string = "success") {
    UIkit.notification(message, status);
  }

  modalDialog(title: string, message: string) {
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
  }

  getErrorMessage(error: AxiosError) {
    let errormsg = "";

    // If a response was obtained
    if (error.response) {
      // If the response is a nicely formatted JSON response from the server
      if (error.response.data.message) {
        errormsg = `${error.response.status}: ${error.response.data.message}`;
        console.log(errormsg);
      }
      // If the response is just some generic error response
      else {
        errormsg = `${error.response.status}: ${error.response.data}`;
        console.log(errormsg);
      }
      // If the error occured during the request
    } else if (error.request) {
      errormsg = `${error.message}`;
      console.log(errormsg);
      // Everything else
    } else {
      errormsg = `${error.message}`;
      console.log(errormsg);
    }
    return errormsg;
  }

  modalError(error: AxiosError) {
    const errormsg = this.getErrorMessage(error);
    this.$store.commit("setErrorMessage", errormsg);
    UIkit.notification({
      message: `${errormsg}`,
      status: "danger"
    });
  }

  showModalElement(element: HTMLElement) {
    UIkit.modal(element).show();
  }

  hideModalElement(element: HTMLElement) {
    UIkit.modal(element).hide();
  }

  getLocalStorageObj(keyName: string) {
    if (localStorage.getItem(keyName)) {
      try {
        return JSON.parse(localStorage.getItem(keyName) || '{}');
      } catch (e) {
        console.log("Malformed entry. Removing from localStorage");
        localStorage.removeItem(keyName);
        return null;
      }
    }
  }

  setLocalStorageObj(keyName: string, object: any) {
    const parsed = JSON.stringify(object);
    localStorage.setItem(keyName, parsed);
  }

}