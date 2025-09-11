import React, { useState, useMemo } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  Grid,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  InputAdornment,
  Alert,
} from '@mui/material';
import {
  Search,
  Schedule,
  Person,
  LocationOn,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs from 'dayjs';

// Custom IndiGo-style flight icon
const IndigoFlightIcon = ({ sx = {} }) => (
  <Box
    sx={{
      width: 24,
      height: 24,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      ...sx
    }}
  >
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M21 16V14L13 9V3.5C13 2.67 12.33 2 11.5 2S10 2.67 10 3.5V9L2 14V16L10 13.5V19L8 20.5V22L11.5 21L15 22V20.5L13 19V13.5L21 16Z"
        fill="#003DA5"
        stroke="#003DA5"
        strokeWidth="0.5"
      />
    </svg>
  </Box>
);

// Custom dotted arrow component
const DottedArrow = ({ sx = {} }) => (
  <Box
    sx={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      ...sx
    }}
  >
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M8 6L16 12L8 18"
        stroke="#4D4D4D"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray="2,2"
      />
    </svg>
  </Box>
);

const FlightWiseView = ({ flights, currentRoster, crew }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedFlight, setSelectedFlight] = useState(null);
  const [selectedDate, setSelectedDate] = useState(null);

  // Create crew lookup map
  const crewMap = useMemo(() => {
    const map = {};
    crew.forEach(member => {
      map[member.crew_id] = member;
    });
    return map;
  }, [crew]);

  // Create assignments lookup map
  const assignmentsMap = useMemo(() => {
    const map = {};
    if (currentRoster?.assignments) {
      currentRoster.assignments.forEach(assignment => {
        if (!map[assignment.flight_id]) {
          map[assignment.flight_id] = [];
        }
        map[assignment.flight_id].push(assignment);
      });
    }
    return map;
  }, [currentRoster]);

  // Filter flights based on search term, selected date, AND require full crew composition (1 CPT, 1 FO, 1 SC, 4 CC)
  const filteredFlights = useMemo(() => {
    const matchesSearch = (flight) => {
      if (!searchTerm) return true;
      const term = searchTerm.toLowerCase();
      return (
        flight.flight_id?.toLowerCase().includes(term) ||
        flight.dep_airport?.toLowerCase().includes(term) ||
        flight.arr_airport?.toLowerCase().includes(term) ||
        flight.aircraft_type?.toLowerCase().includes(term)
      );
    };

    const matchesDate = (flight) => {
      if (!selectedDate) return true;
      const fDay = dayjs(flight.dep_dt).format('YYYY-MM-DD');
      const sel = dayjs(selectedDate).format('YYYY-MM-DD');
      return fDay === sel;
    };

    const hasFullCrew = (flightId) => {
      const assigns = assignmentsMap[flightId] || [];
      if (assigns.length !== 7) return false;

      let cpt = 0, fo = 0, sc = 0, cc = 0;
      assigns.forEach(a => {
        const r = normalizeRole(a.role);
        if (r === 'Captain') cpt++;
        else if (r === 'FO') fo++;
        else if (r === 'SC') sc++;
        else if (r === 'CC') cc++;
      });

      return cpt === 1 && fo === 1 && sc === 1 && cc === 4;
    };

    return flights.filter(f => matchesSearch(f) && matchesDate(f) && hasFullCrew(f.flight_id));
  }, [flights, searchTerm, selectedDate, assignmentsMap]);

  // Get crew assignments for a specific flight
  const getFlightAssignments = (flightId) => {
    return assignmentsMap[flightId] || [];
  };

  // Get crew member details
  const getCrewDetails = (crewId) => {
    return crewMap[crewId] || { name: 'Unknown', role: 'Unknown' };
  };

  const handleFlightClick = (flight) => {
    setSelectedFlight(flight);
  };

  const formatDateTime = (dateTime) => {
    if (!dateTime) return 'N/A';
    return new Date(dateTime).toLocaleString();
  };

  function normalizeRole(role) {
    if (!role) return '';
    switch (role) {
      case 'Captain':
        return 'Captain';
      case 'First Officer':
      case 'FO':
        return 'FO';
      case 'Senior Crew':
      case 'SC':
        return 'SC';
      case 'Cabin Crew':
      case 'CC':
        return 'CC';
      default:
        return role;
    }
  };

  const getRoleColor = (role) => {
    const r = normalizeRole(role);
    switch (r) {
      case 'Captain': return 'primary';
      case 'FO': return 'success';
      case 'SC': return 'secondary';
      case 'CC': return 'warning';
      default: return 'default';
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Search Section */}
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <IndigoFlightIcon sx={{ mr: 1 }} />
            <Typography variant="h5" sx={{ color: '#1A1A1A', fontWeight: 600 }}>
              Flight Search & Details
            </Typography>
          </Box>
          
          <TextField
            fullWidth
            placeholder="Search flights by ID, departure/arrival airport, or aircraft type..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
            sx={{ mb: 2 }}
          />

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <DatePicker
              label="Filter by Date"
              value={selectedDate}
              onChange={(d) => setSelectedDate(d)}
              slotProps={{ textField: { size: 'small', sx: { minWidth: 180 } } }}
            />
            <Chip
              label={selectedDate ? dayjs(selectedDate).format('YYYY-MM-DD') : 'All Days'}
              variant="outlined"
              size="small"
            />
            <Chip
              label="Clear Date"
              onClick={() => setSelectedDate(null)}
              size="small"
              variant="outlined"
            />
          </Box>

          <Typography variant="body2" color="text.secondary">
            {filteredFlights.length} flight{filteredFlights.length !== 1 ? 's' : ''} found
          </Typography>
        </CardContent>
      </Card>

      <Grid container spacing={3}>
        {/* Flight List */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: '#1A1A1A' }}>
                Available Flights
              </Typography>
              
              {filteredFlights.length === 0 ? (
                <Alert severity="info">
                  No flights found matching your search criteria.
                </Alert>
              ) : (
                <Box sx={{ maxHeight: 600, overflow: 'auto' }}>
                  {filteredFlights.map((flight) => {
                    const assignments = getFlightAssignments(flight.flight_id);
                    const isSelected = selectedFlight?.flight_id === flight.flight_id;
                    
                    return (
                      <Paper
                        key={flight.flight_id}
                        sx={{
                          p: 2,
                          mb: 1,
                          cursor: 'pointer',
                          border: isSelected ? 2 : 1,
                          borderColor: isSelected ? 'primary.main' : 'divider',
                          '&:hover': {
                            backgroundColor: 'action.hover',
                          },
                        }}
                        onClick={() => handleFlightClick(flight)}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', mr: 2 }}>
                            <IndigoFlightIcon sx={{ mr: 1 }} />
                            <Typography variant="h6" sx={{ color: '#003DA5', fontWeight: 600 }}>
                              {flight.flight_id}
                            </Typography>
                          </Box>
                          <Box sx={{ flexGrow: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography variant="body2" color="text.secondary">
                                {flight.dep_airport}
                              </Typography>
                              <DottedArrow />
                              <Typography variant="body2" color="text.secondary">
                                {flight.arr_airport}
                              </Typography>
                            </Box>
                          </Box>
                          <Chip 
                            label={flight.aircraft_type} 
                            variant="outlined" 
                            size="small" 
                          />
                        </Box>
                        
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Box>
                            <Typography variant="caption" display="block">
                              <Schedule sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                              {formatDateTime(flight.dep_dt)}
                            </Typography>
                          </Box>
                          <Chip 
                            label={`${assignments.length} crew`}
                            color={assignments.length > 0 ? 'success' : 'default'}
                            size="small"
                          />
                        </Box>
                      </Paper>
                    );
                  })}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Flight Details */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: '#1A1A1A' }}>
                Flight Details
              </Typography>
              
              {!selectedFlight ? (
                <Alert severity="info">
                  Select a flight from the list to view detailed information and crew assignments.
                </Alert>
              ) : (
                <Box>
                  {/* Flight Information */}
                  <Paper sx={{ p: 2, mb: 2, bgcolor: 'primary.50' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <IndigoFlightIcon sx={{ mr: 2, width: 32, height: 32 }} />
                      <Box>
                        <Typography variant="h5" sx={{ color: '#003DA5', fontWeight: 600 }}>
                          {selectedFlight.flight_id}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {selectedFlight.aircraft_type}
                        </Typography>
                      </Box>
                    </Box>
                    
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                          <LocationOn sx={{ mr: 1, color: 'success.main' }} />
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              Departure
                            </Typography>
                            <Typography variant="body1" fontWeight="bold">
                              {selectedFlight.dep_airport}
                            </Typography>
                            <Typography variant="caption">
                              {formatDateTime(selectedFlight.dep_dt)}
                            </Typography>
                          </Box>
                        </Box>
                      </Grid>
                      <Grid item xs={6}>
                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                          <LocationOn sx={{ mr: 1, color: 'error.main' }} />
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              Arrival
                            </Typography>
                            <Typography variant="body1" fontWeight="bold">
                              {selectedFlight.arr_airport}
                            </Typography>
                            <Typography variant="caption">
                              {formatDateTime(selectedFlight.arr_dt)}
                            </Typography>
                          </Box>
                        </Box>
                      </Grid>
                    </Grid>
                  </Paper>

                  {/* Crew Assignments */}
                  <Typography variant="h6" gutterBottom>
                    Crew Assignments
                  </Typography>
                  
                  {(() => {
                    const assignments = getFlightAssignments(selectedFlight.flight_id);
                    
                    if (assignments.length === 0) {
                      return (
                        <Alert severity="warning">
                          No crew assigned to this flight.
                        </Alert>
                      );
                    }

                    return (
                      <TableContainer component={Paper} variant="outlined">
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell>Crew ID</TableCell>
                              <TableCell>Name</TableCell>
                              <TableCell>Role</TableCell>
                              <TableCell>Base</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {assignments.map((assignment, index) => {
                              const crewDetails = getCrewDetails(assignment.crew_id);
                              return (
                                <TableRow key={`${assignment.crew_id}-${index}`}>
                                  <TableCell>{assignment.crew_id}</TableCell>
                                  <TableCell>
                                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                      <Person sx={{ mr: 1, fontSize: 16 }} />
                                      {crewDetails.name || 'Unknown'}
                                    </Box>
                                  </TableCell>
                                  <TableCell>
                                    <Chip 
                                      label={assignment.role} 
                                      color={getRoleColor(assignment.role)}
                                      size="small"
                                    />
                                  </TableCell>
                                  <TableCell>{crewDetails.base || 'N/A'}</TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    );
                  })()}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default FlightWiseView;
