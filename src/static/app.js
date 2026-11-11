document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const messageDiv = document.getElementById("message");
  const signupContainer = document.getElementById("signup-container");
  const accountButton = document.getElementById("account-button");
  const accountMenu = document.getElementById("account-menu");
  const loginButton = document.getElementById("login-button");
  const logoutButton = document.getElementById("logout-button");
  const loginDialog = document.getElementById("login-dialog");
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  let teacherSession = null;

  function escapeHTML(value) {
    const element = document.createElement("span");
    element.textContent = value;
    return element.innerHTML.replaceAll('"', "&quot;");
  }

  function setTeacher(session) {
    teacherSession = session;
    signupContainer.hidden = !session;
    loginButton.hidden = Boolean(session);
    logoutButton.hidden = !session;
    document.getElementById("account-name").textContent = session
      ? session.username
      : "Student view";
    signupForm.reset();
  }

  function closeAccountMenu() {
    accountMenu.hidden = true;
    accountButton.setAttribute("aria-expanded", "false");
  }

  accountButton.addEventListener("click", () => {
    accountMenu.hidden = !accountMenu.hidden;
    accountButton.setAttribute("aria-expanded", String(!accountMenu.hidden));
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".account-controls")) closeAccountMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeAccountMenu();
  });
  loginButton.addEventListener("click", () => {
    closeAccountMenu();
    loginError.hidden = true;
    loginDialog.showModal();
  });
  document.getElementById("close-login").addEventListener("click", () => loginDialog.close());
  loginDialog.addEventListener("close", () => loginForm.reset());

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = document.getElementById("login-submit");
    submit.disabled = true;
    loginError.hidden = true;
    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: document.getElementById("username").value,
          password: document.getElementById("password").value,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Unable to log in");
      setTeacher(result);
      loginDialog.close();
      await fetchActivities();
    } catch (error) {
      loginError.textContent = error.message;
      loginError.hidden = false;
      document.getElementById("password").value = "";
    } finally {
      submit.disabled = false;
    }
  });

  logoutButton.addEventListener("click", async () => {
    logoutButton.disabled = true;
    try {
      const response = await fetch("/auth/logout", {
        method: "POST",
        headers: { "X-CSRF-Token": teacherSession.csrf_token },
      });
      if (!response.ok && response.status !== 401) throw new Error("Unable to log out. Please retry.");
      setTeacher(null);
      closeAccountMenu();
      await fetchActivities();
    } catch (error) {
      messageDiv.textContent = error.message;
      messageDiv.className = "message error";
    } finally {
      logoutButton.disabled = false;
    }
  });

  async function checkSession(response) {
    if (response.status === 401 || response.status === 403) {
      setTeacher(null);
      await fetchActivities();
    }
  }

  // Function to fetch activities from API
  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      if (!response.ok) throw new Error("Unable to load activities");
      const activities = await response.json();

      // Clear loading message
      activitiesList.innerHTML = "";
      const selectedActivity = activitySelect.value;
      activitySelect.replaceChildren(new Option("-- Select an activity --", ""));

      // Populate activities list
      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";

        const spotsLeft =
          details.max_participants - details.participants.length;

        // Create participants HTML with delete icons instead of bullet points
        const participantsHTML =
          details.participants.length > 0
            ? `<div class="participants-section">
              <h5>Participants:</h5>
              <ul class="participants-list">
                ${details.participants
                  .map(
                    (email) =>
                      `<li><span class="participant-email">${escapeHTML(email)}</span>${teacherSession ? `<button class="delete-btn" data-activity="${escapeHTML(name)}" data-email="${escapeHTML(email)}" aria-label="Unregister ${escapeHTML(email)}" title="Unregister student"><img src="trash-2.svg" width="18" height="18" alt="" /></button>` : ""}</li>`
                  )
                  .join("")}
              </ul>
            </div>`
            : `<p><em>No participants yet</em></p>`;

        activityCard.innerHTML = `
          <h4>${escapeHTML(name)}</h4>
          <p>${escapeHTML(details.description)}</p>
          <p><strong>Schedule:</strong> ${escapeHTML(details.schedule)}</p>
          <p><strong>Availability:</strong> ${spotsLeft} spots left</p>
          <div class="participants-container">
            ${participantsHTML}
          </div>
        `;

        activitiesList.appendChild(activityCard);

        // Add option to select dropdown
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });
      activitySelect.value = selectedActivity;

      // Add event listeners to delete buttons
      document.querySelectorAll(".delete-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });
    } catch (error) {
      activitiesList.innerHTML =
        "<p>Failed to load activities. Please try again later.</p>";
      console.error("Error fetching activities:", error);
    }
  }

  // Handle unregister functionality
  async function handleUnregister(event) {
    const button = event.currentTarget;
    const activity = button.getAttribute("data-activity");
    const email = button.getAttribute("data-email");
    if (!teacherSession) return;
    button.disabled = true;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/unregister?email=${encodeURIComponent(email)}`,
        {
          method: "DELETE",
          headers: { "X-CSRF-Token": teacherSession.csrf_token },
        }
      );

      const result = await response.json();
      await checkSession(response);

      if (response.ok) {
        messageDiv.textContent = result.message;
        messageDiv.className = "success";

        // Refresh activities list to show updated participants
        fetchActivities();
      } else {
        messageDiv.textContent = result.detail || "An error occurred";
        messageDiv.className = "error";
      }

      messageDiv.classList.remove("hidden");

      // Hide message after 5 seconds
      setTimeout(() => {
        messageDiv.classList.add("hidden");
      }, 5000);
    } catch (error) {
      messageDiv.textContent = "Failed to unregister. Please try again.";
      messageDiv.className = "error";
      messageDiv.classList.remove("hidden");
      console.error("Error unregistering:", error);
    } finally {
      button.disabled = false;
    }
  }

  // Handle form submission
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!teacherSession) return;
    const submit = signupForm.querySelector('button[type="submit"]');
    submit.disabled = true;

    const email = document.getElementById("email").value;
    const activity = document.getElementById("activity").value;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/signup?email=${encodeURIComponent(email)}`,
        {
          method: "POST",
          headers: { "X-CSRF-Token": teacherSession.csrf_token },
        }
      );

      const result = await response.json();
      await checkSession(response);

      if (response.ok) {
        messageDiv.textContent = result.message;
        messageDiv.className = "success";
        signupForm.reset();

        // Refresh activities list to show updated participants
        fetchActivities();
      } else {
        messageDiv.textContent = result.detail || "An error occurred";
        messageDiv.className = "error";
      }

      messageDiv.classList.remove("hidden");

      // Hide message after 5 seconds
      setTimeout(() => {
        messageDiv.classList.add("hidden");
      }, 5000);
    } catch (error) {
      messageDiv.textContent = "Failed to sign up. Please try again.";
      messageDiv.className = "error";
      messageDiv.classList.remove("hidden");
      console.error("Error signing up:", error);
    } finally {
      submit.disabled = false;
    }
  });

  // Initialize app
  async function initialize() {
    try {
      const response = await fetch("/auth/session");
      setTeacher(response.ok ? await response.json() : null);
    } catch {
      setTeacher(null);
    }
    await fetchActivities();
  }
  initialize();
});
