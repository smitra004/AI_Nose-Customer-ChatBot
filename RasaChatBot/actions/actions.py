import requests
from typing import Any, Text, Dict, List, Union # <-- Add Union here

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, UserUtteranceReverted

# --- Define your backend base URL ---
BACKEND_URL = "https://envirosense-ai-backend.onrender.com" # e.g., "http://localhost:3000/api"

# --- Authentication Helper ---
def get_auth_token(tracker: Tracker) -> Union[str, None]:
    """Extracts JWT token from Rasa metadata if available."""
    metadata = tracker.latest_message.get("metadata")
    if metadata and "token" in metadata:
        print("Auth token found in metadata.") # For debugging
        return metadata["token"]
    print("No auth token found.") # For debugging
    return None

# --- Moderation Helper ---
def contains_inappropriate(text: str) -> bool:
    """Basic check for inappropriate words."""
    inappropriate_words = ["badword1", "badword2", "idiot", "stupid"] # Add more
    return any(word in text.lower() for word in inappropriate_words)

# --- Pollutant Knowledge Base ---
# Used only if action_explain_pollutant is triggered (e.g., by logged-out user)
POLLUTANT_DB = {
    "carbon monoxide": "Carbon Monoxide (CO) is a toxic gas produced by incomplete burning of fuels. In high concentrations, it reduces oxygen in the bloodstream.",
    "co": "Carbon Monoxide (CO) is a toxic gas produced by incomplete burning of fuels. In high concentrations, it reduces oxygen in the bloodstream.",
    "sulphur dioxide": "Sulphur Dioxide (SO₂) is a gas from burning fossil fuels like coal and oil. It harms the respiratory system and contributes to acid rain.",
    "so2": "Sulphur Dioxide (SO₂) is a gas from burning fossil fuels like coal and oil. It harms the respiratory system and contributes to acid rain.",
    "ozone": "Ground-level Ozone (O₃) is a major pollutant created when sunlight reacts with emissions from vehicles and industry. It is a key component of smog.",
    "o3": "Ground-level Ozone (O₃) is a major pollutant created when sunlight reacts with emissions from vehicles and industry. It is a key component of smog.",
    "nitrogen dioxide": "Nitrogen Dioxide (NO₂) comes from burning fuel, mainly from vehicles and power plants. It can irritate the respiratory system.",
    "no2": "Nitrogen Dioxide (NO₂) comes from burning fuel, mainly from vehicles and power plants. It can irritate the respiratory system.",
    "pm2.5": "PM2.5 are fine inhalable particles that can travel deep into the respiratory tract, reaching the lungs and causing serious health issues.",
    "pm10": "PM10 are coarse inhalable particles from sources like dust and construction. They can irritate the eyes, nose, and throat."
}

# --- General Knowledge / Fallback Action ---
# Placeholder - Requires setting up Google Search API credentials
class ActionGeneralKnowledgeFallback(Action):
    def name(self) -> Text:
        return "action_general_knowledge_fallback"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get('text')
        print(f"Entering fallback for message: {user_message}") # Debugging

        # Optional: Add simple irrelevance check here if needed
        # if looks_irrelevant(user_message):
        #     dispatcher.utter_message(response="utter_out_of_scope")
        #     return [UserUtteranceReverted()]

        # Placeholder for actual external knowledge API call (e.g., Google Search)
        # For now, just indicate it's out of scope
        dispatcher.utter_message(response="utter_out_of_scope")

        # Revert the user's last message to prevent it affecting dialogue flow
        return [UserUtteranceReverted()]

# --- Action to explain pollutants (can be used by logged-out users) ---
class ActionExplainPollutant(Action):
    def name(self) -> Text:
        return "action_explain_pollutant"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # --- Basic Moderation Check ---
        user_message = tracker.latest_message.get('text')
        if user_message and contains_inappropriate(user_message):
            dispatcher.utter_message(response="utter_moderation_warning")
            return [UserUtteranceReverted()]

        pollutants = list(tracker.get_latest_entity_values("pollutant"))
        print(f"Entities extracted for pollutant explanation: {pollutants}") # Debugging

        if not pollutants:
            # Maybe the NLU failed, try a basic keyword check as a backup
            text = user_message.lower()
            found_keywords = [p for p in POLLUTANT_DB if p in text]
            if found_keywords:
                pollutants = found_keywords
            else:
                 dispatcher.utter_message(text="Which pollutant are you asking about? I know about CO, SO2, Ozone, PM2.5, PM10, etc.")
                 return []


        responses = []
        for p in pollutants:
            description = POLLUTANT_DB.get(p.lower())
            if description:
                responses.append(description)
            else:
                responses.append(f"I don't have specific information on '{p}'.")

        dispatcher.utter_message(text="\n\n".join(responses))
        return []


# --- Actions for Logged-In Users ---

class ActionGetEcoPoints(Action):
    def name(self) -> Text:
        return "action_get_eco_points"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # --- Basic Moderation Check ---
        user_message = tracker.latest_message.get('text')
        if user_message and contains_inappropriate(user_message):
            dispatcher.utter_message(response="utter_moderation_warning")
            return [UserUtteranceReverted()]

        token = get_auth_token(tracker)
        if not token:
            dispatcher.utter_message(response="utter_need_login")
            return []

        headers = {"Authorization": f"Bearer {token}"}
        try:
            print("Attempting to fetch EcoPoints...") # Debugging
            response = requests.get(f"{BACKEND_URL}/users/profile", headers=headers)
            response.raise_for_status()
            data = response.json()
            points = data.get("ecoPoints", 0) # Adjust key based on your API
            dispatcher.utter_message(text=f"You currently have {points} Eco-Points!")
            print(f"Successfully fetched EcoPoints: {points}") # Debugging
        except requests.exceptions.RequestException as e:
            print(f"API Error fetching eco points: {e}")
            dispatcher.utter_message(text="Sorry, I couldn't fetch your Eco-Points right now.")
        return []

class ActionGetMyReports(Action):
    def name(self) -> Text:
        return "action_get_my_reports"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # --- Basic Moderation Check ---
        user_message = tracker.latest_message.get('text')
        if user_message and contains_inappropriate(user_message):
            dispatcher.utter_message(response="utter_moderation_warning")
            return [UserUtteranceReverted()]

        token = get_auth_token(tracker)
        if not token:
            dispatcher.utter_message(response="utter_need_login")
            return []

        headers = {"Authorization": f"Bearer {token}"}
        try:
            print("Attempting to fetch user reports...") # Debugging
            response = requests.get(f"{BACKEND_URL}/reports/mine", headers=headers)
            response.raise_for_status()
            reports = response.json()
            if reports:
                report_list = "\n".join([f"- Report ID: {r.get('id', 'N/A')}, Location: {r.get('location', {}).get('name', 'N/A')}" for r in reports[:5]]) # Adjust keys
                dispatcher.utter_message(text=f"Here are your recent reports:\n{report_list}")
                print("Successfully fetched reports.") # Debugging
            else:
                dispatcher.utter_message(text="You haven't submitted any reports recently.")
                print("No reports found for user.") # Debugging
        except requests.exceptions.RequestException as e:
            print(f"API Error fetching reports: {e}")
            dispatcher.utter_message(text="Sorry, I couldn't fetch your reports right now.")
        return []

class ActionGetDailyMission(Action):
    def name(self) -> Text:
        return "action_get_daily_mission"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # --- Basic Moderation Check ---
        user_message = tracker.latest_message.get('text')
        if user_message and contains_inappropriate(user_message):
            dispatcher.utter_message(response="utter_moderation_warning")
            return [UserUtteranceReverted()]

        token = get_auth_token(tracker)
        if not token:
            dispatcher.utter_message(response="utter_need_login")
            return []

        headers = {"Authorization": f"Bearer {token}"}
        try:
            print("Attempting to fetch daily mission...") # Debugging
            response = requests.get(f"{BACKEND_URL}/missions/today", headers=headers)
            response.raise_for_status()
            mission = response.json()
            mission_desc = mission.get("description", "No mission assigned today.") # Adjust key
            dispatcher.utter_message(text=f"Today's mission: {mission_desc}")
            print(f"Successfully fetched mission: {mission_desc}") # Debugging
        except requests.exceptions.RequestException as e:
            print(f"API Error fetching mission: {e}")
            dispatcher.utter_message(text="Sorry, I couldn't fetch your daily mission right now.")
        return []

class ActionGetLeaderboardTop(Action):
    def name(self) -> Text:
        return "action_get_leaderboard_top"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # --- Basic Moderation Check ---
        user_message = tracker.latest_message.get('text')
        if user_message and contains_inappropriate(user_message):
            dispatcher.utter_message(response="utter_moderation_warning")
            return [UserUtteranceReverted()]

        # Leaderboard might be public, adjust if authentication is needed
        # token = get_auth_token(tracker)
        # headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            print("Attempting to fetch leaderboard...") # Debugging
            response = requests.get(f"{BACKEND_URL}/users/leaderboard")
            response.raise_for_status()
            leaderboard = response.json()
            if leaderboard:
                top_users = "\n".join([f"- {i+1}. {u.get('username', 'N/A')} ({u.get('ecoPoints', 0)} points)" for i, u in enumerate(leaderboard[:3])]) # Adjust keys
                dispatcher.utter_message(text=f"Here are the current top contributors:\n{top_users}")
                print("Successfully fetched leaderboard.") # Debugging
            else:
                dispatcher.utter_message(text="The leaderboard is currently empty.")
                print("Leaderboard is empty.") # Debugging
        except requests.exceptions.RequestException as e:
            print(f"API Error fetching leaderboard: {e}")
            dispatcher.utter_message(text="Sorry, I couldn't fetch the leaderboard right now.")
        return []

# --- Action for reporting symptom (runs AFTER symptom_form) ---
class ActionReportSymptom(Action):
    def name(self) -> Text:
        return "action_report_symptom"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        token = get_auth_token(tracker)
        if not token:
            dispatcher.utter_message(response="utter_need_login")
            # Also reset slot if form failed due to no login
            return [SlotSet("symptom", None)]

        symptom = tracker.get_slot("symptom")
        if not symptom:
             # Should ideally not happen if form works, but good to check
             dispatcher.utter_message(text="I seem to have missed the symptom. Could you please try reporting it again?")
             return []

        headers = {"Authorization": f"Bearer {token}"}
        # Adjust API endpoint and payload structure as needed
        payload = {"symptom": symptom, "timestamp": datetime.datetime.now().isoformat()}
        try:
            print(f"Attempting to POST symptom: {symptom}") # Debugging
            response = requests.post(f"{BACKEND_URL}/health/report", headers=headers, json=payload)
            response.raise_for_status()
            dispatcher.utter_message(text=f"Got it. I've logged your symptom: '{symptom}'. Thank you for contributing!")
            print("Successfully POSTed symptom.") # Debugging
        except requests.exceptions.RequestException as e:
            print(f"API Error reporting symptom: {e}")
            dispatcher.utter_message(text=f"Sorry, I couldn't log your symptom '{symptom}' right now. Please try again later.")
        # Reset slot after use
        return [SlotSet("symptom", None)]


# --- Action for creating health report (runs AFTER health_report_form) ---
class ActionCreateHealthReport(Action):
    def name(self) -> Text:
        return "action_create_health_report"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        token = get_auth_token(tracker)
        if not token:
            dispatcher.utter_message(response="utter_need_login")
            return [SlotSet("report_location", None)] # Reset slot

        location = tracker.get_slot("report_location")
        # Add other slots if your form collects more info (e.g., description)
        if not location:
             dispatcher.utter_message(text="I seem to have missed the location. Could you please try creating the report again?")
             return []

        headers = {"Authorization": f"Bearer {token}"}
        # Adjust API endpoint and payload structure
        payload = {"location": location, "details": "Report created via chatbot"} # Add other details
        try:
            print(f"Attempting to POST health report for location: {location}") # Debugging
            response = requests.post(f"{BACKEND_URL}/reports", headers=headers, json=payload)
            response.raise_for_status()
            # Maybe get report ID from response?
            report_id = response.json().get("id", "N/A")
            dispatcher.utter_message(text=f"Okay, I've created a new health report (ID: {report_id}) for {location}. You can add more details on the website.")
            print("Successfully POSTed health report.") # Debugging
        except requests.exceptions.RequestException as e:
            print(f"API Error creating health report: {e}")
            dispatcher.utter_message(text=f"Sorry, I couldn't create the health report for {location} right now.")
        # Reset slots
        return [SlotSet("report_location", None)]


# --- Action for sending connection request (runs AFTER connection_form) ---
class ActionSendConnectionRequest(Action):
    def name(self) -> Text:
        return "action_send_connection_request"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        token = get_auth_token(tracker)
        if not token:
            dispatcher.utter_message(response="utter_need_login")
            return [SlotSet("connection_recipient", None)] # Reset slot

        recipient_username = tracker.get_slot("connection_recipient")
        if not recipient_username:
             dispatcher.utter_message(text="I seem to have missed the username. Who did you want to connect with?")
             return []

        headers = {"Authorization": f"Bearer {token}"}
        # This likely requires a two-step process: Find user ID, then POST request
        try:
            # Step 1: Find user ID (adjust endpoint and query param)
            print(f"Searching for user: {recipient_username}") # Debugging
            search_response = requests.get(f"{BACKEND_URL}/users/search?username={recipient_username}", headers=headers)
            search_response.raise_for_status()
            users = search_response.json()

            if not users:
                dispatcher.utter_message(text=f"Sorry, I couldn't find a user named '{recipient_username}'. Please check the username.")
                return [SlotSet("connection_recipient", None)]

            recipient_id = users[0].get("id") # Assuming first result is correct and API returns ID
            if not recipient_id:
                 dispatcher.utter_message(text="Found the user, but couldn't get their ID.")
                 return [SlotSet("connection_recipient", None)]

            # Step 2: Send connection request (adjust endpoint)
            print(f"Attempting to send connection request to ID: {recipient_id}") # Debugging
            request_response = requests.post(f"{BACKEND_URL}/connections/request/{recipient_id}", headers=headers)
            request_response.raise_for_status()

            dispatcher.utter_message(text=f"Okay, I've sent a connection request to {recipient_username}.")
            print("Successfully sent connection request.") # Debugging

        except requests.exceptions.RequestException as e:
            print(f"API Error sending connection request: {e}")
            # Check for specific errors e.g., 404 Not Found vs 500 Server Error
            dispatcher.utter_message(text=f"Sorry, I couldn't send the connection request to {recipient_username} right now.")

        # Reset slot
        return [SlotSet("connection_recipient", None)]

# --- Action for general health effects (now checks login status) ---
class ActionHealthEffects(Action):
    def name(self) -> Text:
        return "action_health_effects"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # --- Basic Moderation Check ---
        user_message = tracker.latest_message.get('text')
        if user_message and contains_inappropriate(user_message):
            dispatcher.utter_message(response="utter_moderation_warning")
            return [UserUtteranceReverted()]

        token = get_auth_token(tracker)
        if token:
            # Potentially personalized response for logged-in user in future
            dispatcher.utter_message(response="utter_health_effects")
        else:
            # Standard response for logged-out user
             dispatcher.utter_message(response="utter_health_effects")
        return []

# --- Form Validation Actions (Optional but Recommended) ---
# Add basic validation or custom logic if needed. For now, they can just return the slots.

class ValidateSymptomForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_symptom_form"

    def validate_symptom(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> Dict[Text, Any]:
        if isinstance(slot_value, str) and len(slot_value) > 2: # Basic validation
            return {"symptom": slot_value}
        else:
            dispatcher.utter_message(text="That doesn't seem like a valid symptom. Please describe it.")
            return {"symptom": None}

# Create similar Validate classes for health_report_form and connection_form if you need custom validation