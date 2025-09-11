import React, { useState, useMemo } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Grid,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  Divider,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Tabs,
  Tab,
} from '@mui/material';
import {
  Warning,
  PersonOff,
  FlightTakeoff,
  Add,
  Delete,
  Refresh,
  Compare,
  CheckCircle,
  Error,
  Assessment,
  Timeline,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from 'dayjs';
import DisruptionSimulator from './DisruptionSimulator';
import WhatIfComparison from './WhatIfComparison';
import LLMDisruptionChat from './LLMDisruptionChat';

const DisruptionManagement = ({
  flights,
  crew,
  baselineRoster,
  currentRoster,
  whatIfResults,
  onRunScenario,
  loading,
}) => {
  const [sickLeaves, setSickLeaves] = useState([]);
  const [flightDisruptions, setFlightDisruptions] = useState([]);
  const [showSickLeaveDialog, setShowSickLeaveDialog] = useState(false);
  const [showFlightDisruptionDialog, setShowFlightDisruptionDialog] = useState(false);
  const [newSickLeave, setNewSickLeave] = useState({
    crew_id: '',
    sick_date: dayjs(),
    note: '',
  });
  const [newFlightDisruption, setNewFlightDisruption] = useState({
    flight_id: '',
    type: 'delay',
    delay_minutes: 0,
    note: '',
  });
  const [activeTab, setActiveTab] = useState(0);

  // Calculate changes between baseline and current roster
  const rosterChanges = useMemo(() => {
    if (!whatIfResults?.changes) return null;
    return whatIfResults.changes;
  }, [whatIfResults]);

  const handleAddSickLeave = () => {
    if (newSickLeave.crew_id && newSickLeave.sick_date) {
      setSickLeaves([...sickLeaves, {
        ...newSickLeave,
        id: Date.now(),
        sick_date: newSickLeave.sick_date.format('YYYY-MM-DD'),
      }]);
      setNewSickLeave({
        crew_id: '',
        sick_date: dayjs(),
        note: '',
      });
      setShowSickLeaveDialog(false);
    }
  };

  const handleAddFlightDisruption = () => {
    if (newFlightDisruption.flight_id && newFlightDisruption.type) {
      setFlightDisruptions([...flightDisruptions, {
        ...newFlightDisruption,
        id: Date.now(),
      }]);
      setNewFlightDisruption({
        flight_id: '',
        type: 'delay',
        delay_minutes: 0,
        note: '',
      });
      setShowFlightDisruptionDialog(false);
    }
  };

  const handleRemoveSickLeave = (id) => {
    setSickLeaves(sickLeaves.filter(item => item.id !== id));
  };

  const handleRemoveFlightDisruption = (id) => {
    setFlightDisruptions(flightDisruptions.filter(item => item.id !== id));
  };

  const handleRunRerostering = () => {
    const disruptions = {
      crew_sickness: sickLeaves.map(item => ({
        crew_id: item.crew_id,
        sick_date: item.sick_date,
        note: item.note,
      })),
      flight_disruptions: flightDisruptions.map(item => ({
        flight_id: item.flight_id,
        type: item.type,
        delay_minutes: item.delay_minutes,
        note: item.note,
      })),
    };
    
    onRunScenario(disruptions);
  };

  // Merge parsed disruptions from LLM chat into manual lists
  const handleParsedFromChat = (parsed) => {
    if (!parsed) return;
    const { flight_disruptions = [], crew_sickness = [] } = parsed;

    if (Array.isArray(flight_disruptions) && flight_disruptions.length) {
      setFlightDisruptions(prev => [
        ...prev,
        ...flight_disruptions.map(d => ({
          id: Date.now() + Math.random(),
          flight_id: d.flight_id,
          type: d.type === 'cancellation' ? 'cancellation' : 'delay',
          delay_minutes: Number.isFinite(d.delay_minutes) ? d.delay_minutes : 0,
          note: d.note || 'Added via LLM',
        })),
      ]);
    }

    if (Array.isArray(crew_sickness) && crew_sickness.length) {
      setSickLeaves(prev => [
        ...prev,
        ...crew_sickness.map(s => ({
          id: Date.now() + Math.random(),
          crew_id: s.crew_id,
          sick_date: s.sick_date,
          note: s.note || 'Added via LLM',
        })),
      ]);
    }
  };

  const getCrewName = (crewId) => {
    const member = crew.find(c => c.crew_id === crewId);
    return member ? member.name : 'Unknown';
  };

  const getFlightDetails = (flightId) => {
    const flight = flights.find(f => f.flight_id === flightId);
    return flight ? `${flight.dep_airport} → ${flight.arr_airport}` : 'Unknown';
  };

  const getDisruptionIcon = (type) => {
    switch (type) {
      case 'delay': return <Warning color="warning" />;
      case 'cancellation': return <Error color="error" />;
      default: return <Warning />;
    }
  };

  const getDisruptionColor = (type) => {
    switch (type) {
      case 'delay': return 'warning';
      case 'cancellation': return 'error';
      default: return 'default';
    }
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Header */}
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Warning sx={{ mr: 1, color: 'primary.main' }} />
              <Typography variant="h5" sx={{ color: '#1A1A1A', fontWeight: 600 }}>
                Disruption Lab (Manual + LLM)
              </Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">
              Manage disruptions manually or via natural language, and analyze the impact on crew assignments and roster changes.
            </Typography>
          </CardContent>
        </Card>

        {/* Mode Tabs */}
        <Box sx={{ mt: 2 }}>
          <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)}>
            <Tab label="Manual What-If" />
            <Tab label="LLM Disruption Chat" />
          </Tabs>
        </Box>

        {/* Manual Tab */}
        {activeTab === 0 && (
          <>
          
            {/* What-If Scenario Simulator */}
        {baselineRoster && (
          <DisruptionSimulator
            flights={flights}
            crew={crew}
            onRunScenario={onRunScenario}
            loading={loading}
          />
        )}

        {/* What-If Results */}
        {whatIfResults && (
          <WhatIfComparison
            beforeRoster={baselineRoster}
            afterRoster={currentRoster}
            changes={whatIfResults.changes}
          />
        )}

        {/* Manual Disruption Management */}
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Assessment sx={{ mr: 1, color: 'primary.main' }} />
              <Typography variant="h6" sx={{ color: '#1A1A1A', fontWeight: 600 }}>
                Manual Disruption Management
              </Typography>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Manually add sick leaves and flight disruptions for detailed analysis.
            </Typography>
          </CardContent>
        </Card>

        <Grid container spacing={3}>
          {/* Sick Leave Management */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6" sx={{ color: '#1A1A1A' }}>
                    Sick Leave Management
                  </Typography>
                  <Button
                    variant="contained"
                    startIcon={<Add />}
                    onClick={() => setShowSickLeaveDialog(true)}
                    size="small"
                  >
                    Add Sick Leave
                  </Button>
                </Box>

                {sickLeaves.length === 0 ? (
                  <Alert severity="info">
                    No sick leaves added. Click "Add Sick Leave" to add crew members who are unavailable.
                  </Alert>
                ) : (
                  <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Crew ID</TableCell>
                          <TableCell>Name</TableCell>
                          <TableCell>Date</TableCell>
                          <TableCell>Note</TableCell>
                          <TableCell>Action</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {sickLeaves.map((item) => (
                          <TableRow key={item.id}>
                            <TableCell>{item.crew_id}</TableCell>
                            <TableCell>{getCrewName(item.crew_id)}</TableCell>
                            <TableCell>{item.sick_date}</TableCell>
                            <TableCell>{item.note || 'N/A'}</TableCell>
                            <TableCell>
                              <IconButton
                                size="small"
                                color="error"
                                onClick={() => handleRemoveSickLeave(item.id)}
                              >
                                <Delete />
                              </IconButton>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Flight Disruption Management */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6" sx={{ color: '#1A1A1A' }}>
                    Flight Disruptions
                  </Typography>
                  <Button
                    variant="contained"
                    startIcon={<Add />}
                    onClick={() => setShowFlightDisruptionDialog(true)}
                    size="small"
                  >
                    Add Disruption
                  </Button>
                </Box>

                {flightDisruptions.length === 0 ? (
                  <Alert severity="info">
                    No flight disruptions added. Click "Add Disruption" to add flight delays or cancellations.
                  </Alert>
                ) : (
                  <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Flight</TableCell>
                          <TableCell>Type</TableCell>
                          <TableCell>Delay</TableCell>
                          <TableCell>Note</TableCell>
                          <TableCell>Action</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {flightDisruptions.map((item) => (
                          <TableRow key={item.id}>
                            <TableCell>
                              <Box>
                                <Typography variant="body2" fontWeight="bold">
                                  {item.flight_id}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {getFlightDetails(item.flight_id)}
                                </Typography>
                              </Box>
                            </TableCell>
                            <TableCell>
                              <Chip
                                icon={getDisruptionIcon(item.type)}
                                label={item.type}
                                color={getDisruptionColor(item.type)}
                                size="small"
                              />
                            </TableCell>
                            <TableCell>
                              {item.type === 'delay' ? `${item.delay_minutes} min` : 'N/A'}
                            </TableCell>
                            <TableCell>{item.note || 'N/A'}</TableCell>
                            <TableCell>
                              <IconButton
                                size="small"
                                color="error"
                                onClick={() => handleRemoveFlightDisruption(item.id)}
                              >
                                <Delete />
                              </IconButton>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Rerostering Controls */}
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ color: '#1A1A1A' }}>
                Manual Rerostering Actions
              </Typography>
              <Button
                variant="contained"
                color="primary"
                startIcon={<Refresh />}
                onClick={handleRunRerostering}
                disabled={loading || (!sickLeaves.length && !flightDisruptions.length)}
                size="large"
              >
                Run Manual Rerostering
              </Button>
            </Box>
            
            <Typography variant="body2" color="text.secondary">
              {sickLeaves.length + flightDisruptions.length} manual disruption(s) will be applied to the roster.
            </Typography>
          </CardContent>
        </Card>

        {/* Manual Rerostering Impact Analysis */}
        {rosterChanges && (
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Timeline sx={{ mr: 1, color: 'primary.main' }} />
                <Typography variant="h6" sx={{ color: '#1A1A1A', fontWeight: 600 }}>
                  Manual Rerostering Impact Analysis
                </Typography>
              </Box>

              <Grid container spacing={3}>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <Typography variant="h4" color="primary">
                      {rosterChanges.summary?.total_changes || 0}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Changes
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <Typography variant="h4" color="error">
                      {rosterChanges.summary?.assignments_removed || 0}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Assignments Removed
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <Typography variant="h4" color="success">
                      {rosterChanges.summary?.assignments_added || 0}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Assignments Added
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>

              <Divider sx={{ my: 2 }} />

              {/* Detailed Changes */}
              <Typography variant="h6" gutterBottom sx={{ color: '#1A1A1A' }}>
                Detailed Changes
              </Typography>
              
              {rosterChanges.crew_changes?.length > 0 ? (
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Type</TableCell>
                        <TableCell>Crew ID</TableCell>
                        <TableCell>Flight</TableCell>
                        <TableCell>Role</TableCell>
                        <TableCell>Details</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {rosterChanges.crew_changes.map((change, index) => (
                        <TableRow key={index}>
                          <TableCell>
                            <Chip
                              icon={change.type === 'removed' ? <Error /> : <CheckCircle />}
                              label={change.type}
                              color={change.type === 'removed' ? 'error' : 'success'}
                              size="small"
                            />
                          </TableCell>
                          <TableCell>{change.crew_id}</TableCell>
                          <TableCell>{change.flight_id}</TableCell>
                          <TableCell>{change.role}</TableCell>
                          <TableCell>{change.flight_details}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Alert severity="info">
                  No crew assignment changes detected.
                </Alert>
              )}
            </CardContent>
          </Card>
        )}

          </>
        )}

        {/* LLM Chat Tab */}
        {activeTab === 1 && (
          <>
            <LLMDisruptionChat
              flights={flights}
              crew={crew}
              onParsed={handleParsedFromChat}
              onRunScenario={onRunScenario}
              loading={loading}
            />
            {whatIfResults && (
              <WhatIfComparison
                beforeRoster={baselineRoster}
                afterRoster={currentRoster}
                changes={whatIfResults.changes}
              />
            )}
          </>
        )}

        {/* Sick Leave Dialog */}
        <Dialog open={showSickLeaveDialog} onClose={() => setShowSickLeaveDialog(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Add Sick Leave</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
              <FormControl fullWidth>
                <InputLabel>Crew Member</InputLabel>
                <Select
                  value={newSickLeave.crew_id}
                  onChange={(e) => setNewSickLeave({ ...newSickLeave, crew_id: e.target.value })}
                  label="Crew Member"
                >
                  {crew.map((member) => (
                    <MenuItem key={member.crew_id} value={member.crew_id}>
                      {member.crew_id} - {member.name} ({member.role})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              
              <DatePicker
                label="Sick Date"
                value={newSickLeave.sick_date}
                onChange={(date) => setNewSickLeave({ ...newSickLeave, sick_date: date })}
                renderInput={(params) => <TextField {...params} fullWidth />}
              />
              
              <TextField
                label="Note (Optional)"
                value={newSickLeave.note}
                onChange={(e) => setNewSickLeave({ ...newSickLeave, note: e.target.value })}
                fullWidth
                multiline
                rows={2}
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setShowSickLeaveDialog(false)}>Cancel</Button>
            <Button onClick={handleAddSickLeave} variant="contained">Add</Button>
          </DialogActions>
        </Dialog>

        {/* Flight Disruption Dialog */}
        <Dialog open={showFlightDisruptionDialog} onClose={() => setShowFlightDisruptionDialog(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Add Flight Disruption</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
              <FormControl fullWidth>
                <InputLabel>Flight</InputLabel>
                <Select
                  value={newFlightDisruption.flight_id}
                  onChange={(e) => setNewFlightDisruption({ ...newFlightDisruption, flight_id: e.target.value })}
                  label="Flight"
                >
                  {flights.map((flight) => (
                    <MenuItem key={flight.flight_id} value={flight.flight_id}>
                      {flight.flight_id} - {flight.dep_airport} → {flight.arr_airport}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              
              <FormControl fullWidth>
                <InputLabel>Disruption Type</InputLabel>
                <Select
                  value={newFlightDisruption.type}
                  onChange={(e) => setNewFlightDisruption({ ...newFlightDisruption, type: e.target.value })}
                  label="Disruption Type"
                >
                  <MenuItem value="delay">Delay</MenuItem>
                  <MenuItem value="cancellation">Cancellation</MenuItem>
                </Select>
              </FormControl>
              
              {newFlightDisruption.type === 'delay' && (
                <TextField
                  label="Delay (minutes)"
                  type="number"
                  value={newFlightDisruption.delay_minutes}
                  onChange={(e) => setNewFlightDisruption({ ...newFlightDisruption, delay_minutes: parseInt(e.target.value) || 0 })}
                  fullWidth
                />
              )}
              
              <TextField
                label="Note (Optional)"
                value={newFlightDisruption.note}
                onChange={(e) => setNewFlightDisruption({ ...newFlightDisruption, note: e.target.value })}
                fullWidth
                multiline
                rows={2}
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setShowFlightDisruptionDialog(false)}>Cancel</Button>
            <Button onClick={handleAddFlightDisruption} variant="contained">Add</Button>
          </DialogActions>
        </Dialog>
      </Box>
    </LocalizationProvider>
  );
};

export default DisruptionManagement;
