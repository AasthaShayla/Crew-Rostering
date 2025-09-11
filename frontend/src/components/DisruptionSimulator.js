import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Button,
  Box,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Chip,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Alert,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { 
  Add, 
  Delete, 
  FlightTakeoff, 
  PersonOff, 
  PlayArrow,
  Warning,
  Schedule,
  Cancel 
} from '@mui/icons-material';
import dayjs from 'dayjs';

const DisruptionSimulator = ({ flights, crew, onRunScenario, loading }) => {
  const [flightDisruptions, setFlightDisruptions] = useState([]);
  const [crewSickness, setCrewSickness] = useState([]);
  
  // Form states for adding new disruptions
  const [newFlightDisruption, setNewFlightDisruption] = useState({
    flight_id: '',
    disruption_type: 'Delay',
    delay_minutes: 60,
  });
  
  const [newCrewSickness, setNewCrewSickness] = useState({
    crew_id: '',
    sick_date: dayjs('2025-09-08'),
  });

  const addFlightDisruption = () => {
    if (!newFlightDisruption.flight_id) return;
    
    const disruption = {
      ...newFlightDisruption,
      id: Date.now(),
    };
    
    setFlightDisruptions(prev => [...prev, disruption]);
    setNewFlightDisruption({
      flight_id: '',
      disruption_type: 'Delay',
      delay_minutes: 60,
    });
  };

  const removeFlightDisruption = (id) => {
    setFlightDisruptions(prev => prev.filter(d => d.id !== id));
  };

  const addCrewSickness = () => {
    if (!newCrewSickness.crew_id) return;
    
    const sickness = {
      ...newCrewSickness,
      sick_date: newCrewSickness.sick_date.format('YYYY-MM-DD'),
      id: Date.now(),
    };
    
    setCrewSickness(prev => [...prev, sickness]);
    setNewCrewSickness({
      crew_id: '',
      sick_date: dayjs('2025-09-08'),
    });
  };

  const removeCrewSickness = (id) => {
    setCrewSickness(prev => prev.filter(s => s.id !== id));
  };

  const runWhatIfScenario = () => {
    const scenario = {
      flight_disruptions: flightDisruptions.map(({ id, ...rest }) => rest),
      crew_sickness: crewSickness.map(({ id, ...rest }) => rest),
    };
    onRunScenario(scenario);
  };

  const clearAllDisruptions = () => {
    setFlightDisruptions([]);
    setCrewSickness([]);
  };

  const getFlightDisplay = (flightId) => {
    const flight = flights.find(f => f.flight_id === flightId);
    if (!flight) return flightId;
    return `${flight.flight_id} (${flight.dep_airport}→${flight.arr_airport} ${flight.dep_dt?.substring(11, 16) || ''})`;
  };

  const getCrewDisplay = (crewId) => {
    const crewMember = crew.find(c => c.crew_id === crewId);
    if (!crewMember) return crewId;
    return `${crewMember.crew_id} - ${crewMember.name} (${crewMember.role})`;
  };

  const totalDisruptions = flightDisruptions.length + crewSickness.length;

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Warning sx={{ mr: 1, color: 'warning.main' }} />
          <Typography variant="h6" component="h2">
            What-If Scenario Simulator
          </Typography>
          {totalDisruptions > 0 && (
            <Chip 
              label={`${totalDisruptions} disruption${totalDisruptions > 1 ? 's' : ''}`} 
              color="warning" 
              size="small" 
              sx={{ ml: 2 }} 
            />
          )}
        </Box>

        <Alert severity="info" sx={{ mb: 3 }}>
          Simulate operational disruptions to see how they impact crew assignments. 
          Add flight delays/cancellations or crew sickness, then click "Run What-If Scenario" to see the optimized response.
        </Alert>

        <Grid container spacing={3}>
          {/* Flight Disruptions Section */}
          <Grid item xs={12} md={6}>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
              <FlightTakeoff sx={{ mr: 1 }} />
              Flight Disruptions
            </Typography>

            {/* Add Flight Disruption Form */}
            <Box sx={{ mb: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Select Flight</InputLabel>
                    <Select
                      value={newFlightDisruption.flight_id}
                      onChange={(e) => setNewFlightDisruption(prev => ({ 
                        ...prev, 
                        flight_id: e.target.value 
                      }))}
                      label="Select Flight"
                    >
                      {flights.map((flight) => (
                        <MenuItem key={flight.flight_id} value={flight.flight_id}>
                          {getFlightDisplay(flight.flight_id)}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Disruption Type</InputLabel>
                    <Select
                      value={newFlightDisruption.disruption_type}
                      onChange={(e) => setNewFlightDisruption(prev => ({ 
                        ...prev, 
                        disruption_type: e.target.value 
                      }))}
                      label="Disruption Type"
                    >
                      <MenuItem value="Delay">
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <Schedule sx={{ mr: 1, fontSize: 'small' }} />
                          Delay
                        </Box>
                      </MenuItem>
                      <MenuItem value="Cancellation">
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <Cancel sx={{ mr: 1, fontSize: 'small' }} />
                          Cancellation
                        </Box>
                      </MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={6}>
                  <TextField
                    label="Delay (minutes)"
                    type="number"
                    size="small"
                    fullWidth
                    value={newFlightDisruption.delay_minutes}
                    onChange={(e) => setNewFlightDisruption(prev => ({ 
                      ...prev, 
                      delay_minutes: parseInt(e.target.value) || 0 
                    }))}
                    disabled={newFlightDisruption.disruption_type === 'Cancellation'}
                    inputProps={{ min: 0, max: 480 }}
                  />
                </Grid>

                <Grid item xs={12}>
                  <Button
                    variant="outlined"
                    startIcon={<Add />}
                    onClick={addFlightDisruption}
                    disabled={!newFlightDisruption.flight_id}
                    fullWidth
                  >
                    Add Flight Disruption
                  </Button>
                </Grid>
              </Grid>
            </Box>

            {/* Flight Disruptions List */}
            <List dense>
              {flightDisruptions.map((disruption) => (
                <ListItem key={disruption.id} divider>
                  <ListItemText
                    primary={getFlightDisplay(disruption.flight_id)}
                    secondary={
                      disruption.disruption_type === 'Cancellation' 
                        ? 'Cancelled' 
                        : `Delayed by ${disruption.delay_minutes} minutes`
                    }
                  />
                  <ListItemSecondaryAction>
                    <IconButton 
                      edge="end" 
                      aria-label="delete"
                      onClick={() => removeFlightDisruption(disruption.id)}
                      size="small"
                    >
                      <Delete />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
              {flightDisruptions.length === 0 && (
                <ListItem>
                  <ListItemText 
                    primary="No flight disruptions" 
                    sx={{ fontStyle: 'italic', color: 'text.secondary' }}
                  />
                </ListItem>
              )}
            </List>
          </Grid>

          {/* Crew Sickness Section */}
          <Grid item xs={12} md={6}>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
              <PersonOff sx={{ mr: 1 }} />
              Crew Sickness
            </Typography>

            {/* Add Crew Sickness Form */}
            <Box sx={{ mb: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Select Crew Member</InputLabel>
                    <Select
                      value={newCrewSickness.crew_id}
                      onChange={(e) => setNewCrewSickness(prev => ({ 
                        ...prev, 
                        crew_id: e.target.value 
                      }))}
                      label="Select Crew Member"
                    >
                      {crew.filter(c => c.leave_status === 'Available').map((crewMember) => (
                        <MenuItem key={crewMember.crew_id} value={crewMember.crew_id}>
                          {getCrewDisplay(crewMember.crew_id)}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12}>
                  <DatePicker
                    label="Sick Date"
                    value={newCrewSickness.sick_date}
                    onChange={(newValue) => setNewCrewSickness(prev => ({ 
                      ...prev, 
                      sick_date: newValue 
                    }))}
                    renderInput={(params) => <TextField {...params} fullWidth size="small" />}
                  />
                </Grid>

                <Grid item xs={12}>
                  <Button
                    variant="outlined"
                    startIcon={<Add />}
                    onClick={addCrewSickness}
                    disabled={!newCrewSickness.crew_id}
                    fullWidth
                  >
                    Add Crew Sickness
                  </Button>
                </Grid>
              </Grid>
            </Box>

            {/* Crew Sickness List */}
            <List dense>
              {crewSickness.map((sickness) => (
                <ListItem key={sickness.id} divider>
                  <ListItemText
                    primary={getCrewDisplay(sickness.crew_id)}
                    secondary={`Sick on ${sickness.sick_date}`}
                  />
                  <ListItemSecondaryAction>
                    <IconButton 
                      edge="end" 
                      aria-label="delete"
                      onClick={() => removeCrewSickness(sickness.id)}
                      size="small"
                    >
                      <Delete />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
              {crewSickness.length === 0 && (
                <ListItem>
                  <ListItemText 
                    primary="No crew sickness" 
                    sx={{ fontStyle: 'italic', color: 'text.secondary' }}
                  />
                </ListItem>
              )}
            </List>
          </Grid>
        </Grid>
      </CardContent>

      <Divider />
      
      <CardActions sx={{ px: 2, py: 2 }}>
        <Button
          variant="contained"
          color="warning"
          startIcon={<PlayArrow />}
          onClick={runWhatIfScenario}
          disabled={loading || totalDisruptions === 0}
          size="large"
        >
          {loading ? 'Running Scenario...' : 'Run What-If Scenario'}
        </Button>

        <Button
          onClick={clearAllDisruptions}
          disabled={totalDisruptions === 0}
          sx={{ ml: 1 }}
        >
          Clear All
        </Button>

        <Box sx={{ ml: 'auto' }}>
          <Typography variant="body2" color="text.secondary">
            {totalDisruptions} total disruption{totalDisruptions !== 1 ? 's' : ''}
          </Typography>
        </Box>
      </CardActions>
    </Card>
  );
};

export default DisruptionSimulator;