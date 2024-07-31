/**
 * This function should be called from a Vue component's "created" hook
 * It will initialise a list of properties from local storage.
 * It then sets up watchers for said properties to sync them back
 * so that next time we load, the values persist.
 *
 * Arguments:
 *   keyName: a string, used as the key in local storage
 *   syncedObject: the object whose data you want to sync (usually `this`)
 *   syncedData: an object, the keys of which set the properties to be synced
 */
export function syncDataWithLocalStorage(keyName, syncedObject, syncedData) {
  const syncedKeys = Object.keys(syncedData);
  // First, we try to retrieve the stored data
  const storedString = localStorage.getItem(keyName);
  if (storedString) {
    const storedValues = JSON.parse(storedString);
    for (const item of syncedKeys) {
      if (item in storedValues) syncedObject[item] = storedValues[item];
    }
  }

  // This function will update local storage with current values
  let updateStoredValues = function() {
    let newData = {};
    for (const item of syncedKeys) {
      newData[item] = syncedObject[item];
    }
    localStorage.setItem(keyName, JSON.stringify(newData));
  };

  // Now, set up watchers to update local storage when things change
  for (const item of syncedKeys) {
    syncedObject.$watch(item, updateStoredValues, { deep: true });
  }
}
