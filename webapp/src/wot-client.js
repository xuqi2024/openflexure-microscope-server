let { Servient, Helpers } = require("@node-wot/core")
let { HttpClientFactory } = require("@node-wot/binding-http")

export const wotStoreModule = {
    namespaced: true,
    state: () => ({
      consumedThings: {},
      servient: null,
      helpers: null
    }),
    mutations: {
      addConsumedThing(state, thingUri, consumedThing) {
        state.consumedThings[thingUri] = consumedThing;
      },
      removeConsumedThing(state, thingUri) {
        delete state.consumedThings[thingUri];
      },
      removeAllConsumedThings(state) {
        state.consumedThings = {};
      },
      setServient(state, servient) {
        state.servient = servient;
      },
      setHelpers(state, helpers) {
        state.helpers = helpers;
      }
    },
    actions: {
        async start({ commit }) {
            // Create the servient and add the HTTP binding
            console.log("Setting up WoT servient...");
            let servient = new Servient();
            servient.addClientFactory(new HttpClientFactory());
            await servient.start()
            let WoTHelpers = new Helpers(servient);
            commit("setServient", servient);
            commit("setHelpers", WoTHelpers);
        },
        async consumeThing({ commit, state }, uri) {
            // Fetch the thing description from the given URI and consume it
            // NB this should only be called once, or we'll duplicate effort.
            // Deduplication should be done elsewhere.
            let td = await state.helpers.fetch(uri);
            let consumedThing = await state.servient.consume(td);
            commit("addConsumedThing", uri, consumedThing);
        }
    },
    getters: {}
};