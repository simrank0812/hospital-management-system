/* Sanjeevani Hospital - small helpers */
(function () {
  "use strict";

  // 1. Ask before destructive actions: <form data-confirm="Are you sure?">
  document.addEventListener("submit", function (event) {
    var message = event.target.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });

  // 2. Fade out success / info messages after a few seconds
  document.querySelectorAll(".alert.alert-success, .alert.alert-info").forEach(function (el) {
    setTimeout(function () {
      if (window.bootstrap && bootstrap.Alert) {
        bootstrap.Alert.getOrCreateInstance(el).close();
      }
    }, 6000);
  });

  // 3. Appointment booking: load the free time slots for the chosen doctor and date
  var doctor = document.getElementById("id_doctor");
  var day = document.getElementById("id_date");
  var slot = document.getElementById("id_time");
  if (doctor && day && slot) {
    var form = doctor.closest("form");
    var urlTemplate = form.getAttribute("data-slots-url"); // e.g. /api/slots/0/
    var selected = (slot.getAttribute("data-selected") || "").slice(0, 5);

    var today = new Date();
    day.min = today.getFullYear() + "-" + String(today.getMonth() + 1).padStart(2, "0") + "-" + String(today.getDate()).padStart(2, "0");

    function addOption(value, label) {
      var option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      slot.appendChild(option);
      return option;
    }

    function pretty(hhmm) {
      var parts = hhmm.split(":").map(Number);
      var suffix = parts[0] >= 12 ? "PM" : "AM";
      var hour = parts[0] % 12 || 12;
      return hour + ":" + String(parts[1]).padStart(2, "0") + " " + suffix;
    }

    function loadSlots() {
      slot.innerHTML = "";
      if (!doctor.value || !day.value) {
        addOption("", "Choose a doctor and date first");
        return;
      }
      addOption("", "Loading times...");
      var url = urlTemplate.replace("/0/", "/" + doctor.value + "/") + "?date=" + encodeURIComponent(day.value);
      fetch(url)
        .then(function (response) { return response.json(); })
        .then(function (data) {
          slot.innerHTML = "";
          if (!data.slots.length) {
            addOption("", "No free times on this day - try another date");
            return;
          }
          addOption("", "Select a time");
          data.slots.forEach(function (value) {
            var option = addOption(value, pretty(value));
            if (value === selected) { option.selected = true; }
          });
          selected = ""; // only pre-select once (after a failed form submit)
        })
        .catch(function () {
          slot.innerHTML = "";
          addOption("", "Could not load times - check your connection");
        });
    }

    doctor.addEventListener("change", loadSlots);
    day.addEventListener("change", loadSlots);
    loadSlots();
  }
})();
