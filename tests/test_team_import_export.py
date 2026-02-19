"""Test for enhanced team import/export with email/phone."""
import os
import pytest
import yaml
import tempfile
from io import BytesIO


def test_load_yaml_with_team_objects(client, temp_data_dir):
    """Test importing YAML with team objects containing email and phone."""
    yaml_content = """
Pool A:
  teams:
    - name: "Team Alpha"
      email: "alpha@example.com"
      phone: "555-1111"
    - name: "Team Beta"
      email: "beta@example.com"
    - Team Gamma
  advance: 2

Pool B:
  - name: "Team Delta"
    email: "delta@example.com"
    phone: "555-2222"
  - Team Epsilon
"""
    
    # Login first
    client.post('/login', data={'username': 'testuser', 'password': 'test'})
    
    # Upload the YAML file
    data = {
        'action': 'load_yaml',
        'yaml_file': (BytesIO(yaml_content.encode('utf-8')), 'teams.yaml')
    }
    response = client.post('/teams', data=data, content_type='multipart/form-data', follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify teams.yaml was created correctly
    teams_path = os.path.join(temp_data_dir, 'teams.yaml')
    assert os.path.exists(teams_path)
    
    with open(teams_path, 'r', encoding='utf-8') as f:
        teams_data = yaml.safe_load(f)
    
    # Check structure
    assert 'Pool A' in teams_data
    assert 'Pool B' in teams_data
    assert teams_data['Pool A']['teams'] == ['Team Alpha', 'Team Beta', 'Team Gamma']
    assert teams_data['Pool B']['teams'] == ['Team Delta', 'Team Epsilon']
    assert teams_data['Pool A']['advance'] == 2
    assert teams_data['Pool B']['advance'] == 2
    
    # Verify registrations.yaml was created with contact info
    reg_path = os.path.join(temp_data_dir, 'registrations.yaml')
    assert os.path.exists(reg_path)
    
    with open(reg_path, 'r', encoding='utf-8') as f:
        reg_data = yaml.safe_load(f)
    
    # Check registrations
    teams_reg = {t['team_name']: t for t in reg_data['teams']}
    
    assert 'Team Alpha' in teams_reg
    assert teams_reg['Team Alpha']['email'] == 'alpha@example.com'
    assert teams_reg['Team Alpha']['phone'] == '555-1111'
    assert teams_reg['Team Alpha']['status'] == 'assigned'
    assert teams_reg['Team Alpha']['assigned_pool'] == 'Pool A'
    
    assert 'Team Beta' in teams_reg
    assert teams_reg['Team Beta']['email'] == 'beta@example.com'
    assert teams_reg['Team Beta']['status'] == 'assigned'
    
    assert 'Team Delta' in teams_reg
    assert teams_reg['Team Delta']['email'] == 'delta@example.com'
    assert teams_reg['Team Delta']['phone'] == '555-2222'
    
    # Teams without contact info should not be in registrations
    assert 'Team Gamma' not in teams_reg
    assert 'Team Epsilon' not in teams_reg


def test_export_teams_with_registrations(client, temp_data_dir):
    """Test exporting teams merges data from teams.yaml and registrations.yaml."""
    # Setup test data
    teams_data = {
        'Pool A': {
            'teams': ['Team Alpha', 'Team Beta', 'Team Gamma'],
            'advance': 2
        }
    }
    
    registrations_data = {
        'registration_open': False,
        'teams': [
            {
                'team_name': 'Team Alpha',
                'email': 'alpha@example.com',
                'phone': '555-1111',
                'status': 'assigned',
                'assigned_pool': 'Pool A'
            },
            {
                'team_name': 'Team Beta',
                'email': 'beta@example.com',
                'phone': '',
                'status': 'assigned',
                'assigned_pool': 'Pool A'
            }
        ]
    }
    
    teams_path = os.path.join(temp_data_dir, 'teams.yaml')
    with open(teams_path, 'w', encoding='utf-8') as f:
        yaml.dump(teams_data, f, default_flow_style=False)
    
    reg_path = os.path.join(temp_data_dir, 'registrations.yaml')
    with open(reg_path, 'w', encoding='utf-8') as f:
        yaml.dump(registrations_data, f, default_flow_style=False)
    
    # Login first
    client.post('/login', data={'username': 'testuser', 'password': 'test'})
    
    # Call export endpoint
    response = client.get('/api/export-teams')
    
    assert response.status_code == 200
    assert response.content_type == 'application/x-yaml'
    
    # Parse the exported YAML
    export_data = yaml.safe_load(response.data)
    
    # Verify structure
    assert 'Pool A' in export_data
    teams_list = export_data['Pool A']['teams']
    
    # Team Alpha should have email and phone
    assert isinstance(teams_list[0], dict)
    assert teams_list[0]['name'] == 'Team Alpha'
    assert teams_list[0]['email'] == 'alpha@example.com'
    assert teams_list[0]['phone'] == '555-1111'
    
    # Team Beta should have email but no phone (empty string not exported)
    assert isinstance(teams_list[1], dict)
    assert teams_list[1]['name'] == 'Team Beta'
    assert teams_list[1]['email'] == 'beta@example.com'
    assert 'phone' not in teams_list[1]
    
    # Team Gamma has no registration, should be a simple string
    assert isinstance(teams_list[2], str)
    assert teams_list[2] == 'Team Gamma'


def test_backward_compatibility_simple_strings(client, temp_data_dir):
    """Test that simple string format still works (backward compatibility)."""
    yaml_content = """
Pool A:
  - Team 1
  - Team 2

Pool B:
  teams:
    - Team 3
    - Team 4
  advance: 3
"""
    
    # Login first
    client.post('/login', data={'username': 'testuser', 'password': 'test'})
    
    # Upload the YAML file
    data = {
        'action': 'load_yaml',
        'yaml_file': (BytesIO(yaml_content.encode('utf-8')), 'teams.yaml')
    }
    response = client.post('/teams', data=data, content_type='multipart/form-data', follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify teams.yaml
    teams_path = os.path.join(temp_data_dir, 'teams.yaml')
    with open(teams_path, 'r', encoding='utf-8') as f:
        teams_data = yaml.safe_load(f)
    
    assert teams_data['Pool A']['teams'] == ['Team 1', 'Team 2']
    assert teams_data['Pool A']['advance'] == 2  # Default
    assert teams_data['Pool B']['teams'] == ['Team 3', 'Team 4']
    assert teams_data['Pool B']['advance'] == 3  # Specified
    
    # Verify no registrations were created
    reg_path = os.path.join(temp_data_dir, 'registrations.yaml')
    if os.path.exists(reg_path):
        with open(reg_path, 'r', encoding='utf-8') as f:
            reg_data = yaml.safe_load(f)
        assert len(reg_data.get('teams', [])) == 0
