# Payment Tracking API Usage Examples

This document provides examples of how to use the payment tracking endpoints.

## Prerequisites
- User must be authenticated (logged in)
- Teams must be registered in the system

## API Endpoints

### 1. Toggle Payment Status

Mark a team as paid or unpaid (toggles the current status).

**Endpoint:** `POST /api/toggle-paid`

**Request:**
```json
{
  "team_name": "Team Alpha"
}
```

**Response (Success):**
```json
{
  "success": true,
  "paid": true
}
```

**Response (Error - Team Not Found):**
```json
{
  "success": false,
  "error": "Team not found in registrations."
}
```

**Status Codes:**
- 200: Success
- 400: Bad request (missing team_name)
- 404: Team not found

### 2. Get Unpaid Teams

Retrieve a list of all teams that haven't paid yet, including their contact information.

**Endpoint:** `GET /api/unpaid-teams`

**Response:**
```json
{
  "success": true,
  "unpaid_teams": [
    {
      "team_name": "Team Alpha",
      "email": "alpha@example.com",
      "phone": "+1234567890",
      "status": "assigned",
      "assigned_pool": "Pool A"
    },
    {
      "team_name": "Team Beta",
      "email": "beta@example.com",
      "phone": null,
      "status": "unassigned",
      "assigned_pool": null
    }
  ]
}
```

**Status Codes:**
- 200: Success

## Usage Examples

### JavaScript (Frontend)

```javascript
// Toggle payment status
async function toggleTeamPaid(teamName) {
  const response = await fetch('/api/toggle-paid', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ team_name: teamName })
  });
  
  const data = await response.json();
  if (data.success) {
    console.log(`Team ${teamName} is now ${data.paid ? 'paid' : 'unpaid'}`);
  } else {
    console.error('Error:', data.error);
  }
}

// Get list of unpaid teams
async function getUnpaidTeams() {
  const response = await fetch('/api/unpaid-teams');
  const data = await response.json();
  
  if (data.success) {
    console.log('Unpaid teams:', data.unpaid_teams);
    // Send reminder emails
    data.unpaid_teams.forEach(team => {
      console.log(`Reminder needed for ${team.team_name} at ${team.email}`);
    });
  }
}
```

### Python (Backend/Script)

```python
import requests

# Toggle payment status
def toggle_payment(base_url, team_name, cookies):
    response = requests.post(
        f'{base_url}/api/toggle-paid',
        json={'team_name': team_name},
        cookies=cookies
    )
    data = response.json()
    if data['success']:
        print(f"Team {team_name} is now {'paid' if data['paid'] else 'unpaid'}")
    else:
        print(f"Error: {data['error']}")

# Get unpaid teams
def get_unpaid_teams(base_url, cookies):
    response = requests.get(f'{base_url}/api/unpaid-teams', cookies=cookies)
    data = response.json()
    
    if data['success']:
        for team in data['unpaid_teams']:
            print(f"{team['team_name']}: {team['email']}")
    return data['unpaid_teams']
```

## Data Persistence

- Payment status is stored in `registrations.yaml` under each team's data
- Status persists across application restarts
- Existing teams without the `paid` field are automatically initialized to `False`

## Integration with Existing Features

The payment tracking integrates seamlessly with:
- Team registration workflow
- Pool assignment
- Tournament management

Teams can be marked as paid/unpaid regardless of whether they're assigned to a pool or unassigned.
