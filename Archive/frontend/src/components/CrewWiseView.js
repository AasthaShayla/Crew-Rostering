import React, { useState, useMemo, useEffect, useRef } from 'react';
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
  Avatar,
  LinearProgress,
  InputAdornment,
  Alert,
  Divider,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import {
  Search,
  Person,
  Schedule,
  FlightTakeoff,
  Work,
  Warning,
  CheckCircle,
  NavigateBefore,
  NavigateNext,
  CalendarToday,
} from '@mui/icons-material';
import dayjs from 'dayjs';

// Custom IndiGo-style flight icon
const IndigoFlightIcon = ({ sx = {} }) => (
  <Box
    sx={{
      width: 20,
      height: 20,
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
        d="M21 16V14L13 9V3.5C13 2.67 12.33 2 11.5 2S10 2.67 10 3.5V9L2 14V16L10 13.5V19L8 20.5V22L11.5 21L15 22V20.5L13 19V13.5L21 16Z"
        fill="#003DA5"
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
      width="12"
      height="12"
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

const CrewWiseView = ({ crew, currentRoster, flights }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCrew, setSelectedCrew] = useState(null);
  const [selectedDate, setSelectedDate] = useState(dayjs());
  const [roleFilter, setRoleFilter] = useState('all'); // 'all' | 'Captain' | 'First Officer' | 'Senior Crew' | 'Cabin Crew'
  const detailsRef = useRef(null);

  // Create assignments lookup map
  const assignmentsMap = useMemo(() => {
    const map = {};
    if (currentRoster?.assignments) {
      currentRoster.assignments.forEach(assignment => {
        if (!map[assignment.crew_id]) {
          map[assignment.crew_id] = [];
        }
        map[assignment.crew_id].push(assignment);
      });
    }
    return map;
  }, [currentRoster]);

  // Calculate duty hours for each crew member
  const crewWithDutyHours = useMemo(() => {
    return crew.map(member => {
      const assignments = assignmentsMap[member.crew_id] || [];
      const totalMinutes = assignments.reduce((sum, assignment) => sum + (assignment.duration_min || 0), 0);
      const totalHours = totalMinutes / 60;
      
      // Determine duty level based on hours
      let dutyLevel = 'low';
      let dutyColor = 'success';
      if (totalHours > 8) {
        dutyLevel = 'high';
        dutyColor = 'error';
      } else if (totalHours > 6) {
        dutyLevel = 'medium';
        dutyColor = 'warning';
      }

      return {
        ...member,
        assignments,
        totalHours: Math.round(totalHours * 10) / 10,
        dutyLevel,
        dutyColor,
        flightCount: assignments.length,
      };
    });
  }, [crew, assignmentsMap]);

  // Filter crew based on search term
  const filteredCrew = useMemo(() => {
    let list = crewWithDutyHours;

    // Search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      list = list.filter(member =>
        member.crew_id?.toLowerCase().includes(term) ||
        member.name?.toLowerCase().includes(term) ||
        member.role?.toLowerCase().includes(term) ||
        member.base?.toLowerCase().includes(term)
      );
    }

    // Role filter
    if (roleFilter !== 'all') {
      const rf = String(roleFilter);
      list = list.filter(member => {
        const r = String(member.role || '').trim();
        if (rf === 'First Officer') return r === 'First Officer' || r === 'FO';
        if (rf === 'Senior Crew') return r === 'Senior Crew' || r === 'SC';
        if (rf === 'Cabin Crew') return r === 'Cabin Crew' || r === 'CC';
        return r === 'Captain';
      });
    }

    // Date filter: keep crew who have at least one assignment on selectedDate
    const dateStr = selectedDate ? selectedDate.format('YYYY-MM-DD') : null;
    if (dateStr) {
      list = list.filter(member => {
        const asns = member.assignments || [];
        return asns.some(a => dayjs(a.dep_dt).format('YYYY-MM-DD') === dateStr);
      });
    }

    return list;
  }, [crewWithDutyHours, searchTerm, roleFilter, selectedDate]);

  // Auto-select first crew in filtered list for quick viewing
  useEffect(() => {
    if (!selectedCrew && filteredCrew.length > 0) {
      setSelectedCrew(filteredCrew[0]);
    }
  }, [filteredCrew, selectedCrew]);


  const handleCrewClick = (member) => {
    setSelectedCrew(member);
    // Smoothly focus the details panel
    setTimeout(() => {
      if (detailsRef.current) {
        detailsRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 0);
  };

  const handleDateChange = (newDate) => {
    setSelectedDate(newDate);
  };

  const handlePrevDate = () => {
    setSelectedDate(prev => prev.subtract(1, 'day'));
  };

  const handleNextDate = () => {
    setSelectedDate(prev => prev.add(1, 'day'));
  };

  // Get assignments for selected crew member on selected date
  const getCrewScheduleForDate = (crewMember, date) => {
    if (!crewMember || !currentRoster?.assignments) return [];
    
    const dateStr = date.format('YYYY-MM-DD');
    return crewMember.assignments.filter(assignment => {
      const assignmentDate = dayjs(assignment.dep_dt).format('YYYY-MM-DD');
      return assignmentDate === dateStr;
    }).sort((a, b) => dayjs(a.dep_dt).diff(dayjs(b.dep_dt)));
  };

  const getDutyColor = (level) => {
    switch (level) {
      case 'high': return '#D93025';
      case 'medium': return '#FFB020';
      case 'low': return '#2E8B57';
      default: return '#D9D9D9';
    }
  };

  const getDutyIcon = (level) => {
    switch (level) {
      case 'high': return <Warning color="error" />;
      case 'medium': return <Schedule color="warning" />;
      case 'low': return <CheckCircle color="success" />;
      default: return <Work />;
    }
  };

  const formatDateTime = (dateTime) => {
    if (!dateTime) return 'N/A';
    return new Date(dateTime).toLocaleString();
  };

  function normalizeRole(role) {
    if (!role) return '';
    const r = String(role);
    if (r === 'First Officer' || r === 'FO') return 'FO';
    if (r === 'Senior Crew' || r === 'SC') return 'SC';
    if (r === 'Cabin Crew' || r === 'CC') return 'CC';
    return 'Captain';
  }

  // Safely format qualified_types whether it's an array, JSON string, or plain string
  function formatQualifiedTypes(q) {
    if (!q) return 'N/A';
    if (Array.isArray(q)) return q.join(', ');
    if (typeof q === 'string') {
      try {
        const parsed = JSON.parse(q);
        if (Array.isArray(parsed)) return parsed.join(', ');
      } catch (e) { /* not JSON */ }
      const parts = q.split(/[,\s]+/).filter(Boolean);
      return parts.length ? parts.join(', ') : q;
    }
    return 'N/A';
  }
 
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
            <Person sx={{ mr: 1, color: 'primary.main' }} />
            <Typography variant="h5" sx={{ color: '#1A1A1A', fontWeight: 600 }}>
              Crew Search & Duty Hours
            </Typography>
          </Box>
          
          <TextField
            fullWidth
            placeholder="Search crew by ID, name, role, or base..."
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

          {/* Global filters: Date and Role */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
            <DatePicker
              label="Filter by Date"
              value={selectedDate}
              onChange={(d) => setSelectedDate(d)}
              slotProps={{ textField: { size: 'small', sx: { minWidth: 180 } } }}
            />
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>Role</InputLabel>
              <Select
                value={roleFilter}
                label="Role"
                onChange={(e) => setRoleFilter(e.target.value)}
              >
                <MenuItem value="all">All Roles</MenuItem>
                <MenuItem value="Captain">Captain</MenuItem>
                <MenuItem value="First Officer">First Officer</MenuItem>
                <MenuItem value="Senior Crew">Senior Cabin Crew</MenuItem>
                <MenuItem value="Cabin Crew">Cabin Crew</MenuItem>
              </Select>
            </FormControl>
            <Chip
              label={selectedDate ? selectedDate.format('YYYY-MM-DD') : 'All Days'}
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
            {filteredCrew.length} crew member{filteredCrew.length !== 1 ? 's' : ''} found
          </Typography>
        </CardContent>
      </Card>


      <Grid container spacing={3}>
        {/* Crew List */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: '#1A1A1A' }}>
                Crew Members
              </Typography>
              
              {filteredCrew.length === 0 ? (
                <Alert severity="info">
                  No crew members found matching your search criteria.
                </Alert>
              ) : (
                <Box sx={{ maxHeight: 600, overflow: 'auto' }}>
                  {filteredCrew.map((member) => {
                    const isSelected = selectedCrew?.crew_id === member.crew_id;
                    
                    return (
                      <Paper
                        key={member.crew_id}
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
                        onClick={() => handleCrewClick(member)}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', mr: 2 }}>
                            <Person sx={{ mr: 1, color: '#003DA5' }} />
                            <Typography variant="h6" sx={{ color: '#003DA5', fontWeight: 600 }}>
                              {member.crew_id}
                            </Typography>
                          </Box>
                          <Box sx={{ flexGrow: 1 }}>
                            <Typography variant="body2" color="text.secondary">
                              {member.name || 'Unknown Name'}
                            </Typography>
                          </Box>
                          <Chip 
                            label={member.role} 
                            color={getRoleColor(member.role)}
                            size="small" 
                          />
                        </Box>
                        
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            Base: {member.base || 'N/A'}
                          </Typography>
                          <Chip 
                            label={`${member.flightCount} flights`}
                            color="info"
                            size="small"
                          />
                        </Box>

                        <Box>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                            <Typography variant="body2">
                              Duty Hours: {member.totalHours}h
                            </Typography>
                            <Chip 
                              label={member.dutyLevel.toUpperCase()}
                              color={member.dutyColor}
                              size="small"
                            />
                          </Box>
                          <LinearProgress 
                            variant="determinate" 
                            value={Math.min((member.totalHours / 12) * 100, 100)}
                            color={member.dutyColor}
                            sx={{ height: 6, borderRadius: 3 }}
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

        {/* Crew Details */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h6" sx={{ color: '#1A1A1A' }}>
                  Crew Details & Schedule
                </Typography>
                {selectedCrew && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <IconButton onClick={handlePrevDate} size="small">
                      <NavigateBefore />
                    </IconButton>
                    <DatePicker
                      value={selectedDate}
                      onChange={handleDateChange}
                      slotProps={{
                        textField: {
                          size: 'small',
                          sx: { minWidth: '140px' }
                        }
                      }}
                    />
                    <IconButton onClick={handleNextDate} size="small">
                      <NavigateNext />
                    </IconButton>
                  </Box>
                )}
              </Box>
              
              {!selectedCrew ? (
                <Alert severity="info">
                  Select a crew member from the list to view detailed information and schedule.
                </Alert>
              ) : (
                <Box>
                  {/* Crew Information */}
                  <Paper sx={{ p: 2, mb: 2, bgcolor: 'primary.50' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <Person sx={{ mr: 2, color: '#003DA5', fontSize: 40 }} />
                      <Box>
                        <Typography variant="h5" sx={{ color: '#003DA5', fontWeight: 600 }}>
                          {selectedCrew.crew_id}
                        </Typography>
                        <Typography variant="body1" color="text.secondary">
                          {selectedCrew.name || 'Unknown Name'}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                          <Chip 
                            label={selectedCrew.role} 
                            color={getRoleColor(selectedCrew.role)}
                            size="small"
                          />
                          <Chip 
                            label={`${selectedCrew.totalHours}h duty`}
                            color={selectedCrew.dutyColor}
                            size="small"
                          />
                        </Box>
                      </Box>
                    </Box>
                    
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Base
                        </Typography>
                        <Typography variant="body1" fontWeight="bold">
                          {selectedCrew.base || 'N/A'}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Aircraft Types
                        </Typography>
                        <Typography variant="body1" fontWeight="bold">
                          {formatQualifiedTypes(selectedCrew.qualified_types)}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Max Weekly Hours
                        </Typography>
                        <Typography variant="body1" fontWeight="bold">
                          {selectedCrew.weekly_max_duty_hrs || 'N/A'}h
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Leave Status
                        </Typography>
                        <Typography variant="body1" fontWeight="bold">
                          {selectedCrew.leave_status || 'Available'}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Paper>

                  {/* Daily Schedule */}
                  <Box sx={{ mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                      <CalendarToday sx={{ mr: 1, color: 'primary.main' }} />
                      <Typography variant="h6" sx={{ color: '#1A1A1A' }}>
                        Schedule for {selectedDate.format('MMMM DD, YYYY')}
                      </Typography>
                    </Box>
                    
                    {(() => {
                      const dailyAssignments = getCrewScheduleForDate(selectedCrew, selectedDate);
                      
                      if (dailyAssignments.length === 0) {
                        return (
                          <Alert severity="info">
                            No flight assignments for {selectedCrew.crew_id} on {selectedDate.format('YYYY-MM-DD')}.
                          </Alert>
                        );
                      }
                      
                      return (
                        <TableContainer component={Paper} variant="outlined">
                          <Table size="small">
                            <TableHead>
                              <TableRow>
                                <TableCell>Time</TableCell>
                                <TableCell>Flight</TableCell>
                                <TableCell>Route</TableCell>
                                <TableCell>Duration</TableCell>
                                <TableCell>Role</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {dailyAssignments.map((assignment, index) => (
                                <TableRow key={`${assignment.flight_id}-${index}`}>
                                  <TableCell>
                                    <Box>
                                      <Typography variant="body2" fontWeight="bold">
                                        {dayjs(assignment.dep_dt).format('HH:mm')}
                                      </Typography>
                                      <Typography variant="caption" color="text.secondary">
                                        {dayjs(assignment.arr_dt).format('HH:mm')}
                                      </Typography>
                                    </Box>
                                  </TableCell>
                                  <TableCell>
                                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                      <IndigoFlightIcon sx={{ mr: 1 }} />
                                      {assignment.flight_id}
                                    </Box>
                                  </TableCell>
                                  <TableCell>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                      <Typography variant="body2">
                                        {assignment.dep_airport}
                                      </Typography>
                                      <DottedArrow />
                                      <Typography variant="body2">
                                        {assignment.arr_airport}
                                      </Typography>
                                    </Box>
                                  </TableCell>
                                  <TableCell>
                                    {assignment.duration_min} min
                                  </TableCell>
                                  <TableCell>
                                    <Chip
                                      label={assignment.role || selectedCrew.role}
                                      color={getRoleColor(assignment.role || selectedCrew.role)}
                                      size="small"
                                    />
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      );
                    })()}
                  </Box>

                  {/* Full Schedule (Professional View) - shown when no specific date filter */}
                  {!selectedDate && (
                    <>
                      <Typography variant="h6" gutterBottom sx={{ color: '#1A1A1A' }}>
                        Full Schedule (Professional View)
                      </Typography>

                      {(() => {
                        const grouped = selectedCrew.assignments
                          .slice()
                          .sort((a, b) => dayjs(a.dep_dt).diff(dayjs(b.dep_dt)))
                          .reduce((acc, a) => {
                            const d = dayjs(a.dep_dt).format('YYYY-MM-DD');
                            (acc[d] = acc[d] || []).push(a);
                            return acc;
                          }, {});
                        const days = Object.keys(grouped);
                        if (days.length === 0) {
                          return (
                            <Alert severity="info" sx={{ mb: 2 }}>
                              No assignments available for this crew.
                            </Alert>
                          );
                        }
                        return (
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 2 }}>
                            {days.map((day) => (
                              <Paper key={day} variant="outlined" sx={{ p: 2 }}>
                                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                                  {dayjs(day).format('MMMM DD, YYYY')}
                                </Typography>
                                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                                  {grouped[day].map((a, idx) => (
                                    <Paper
                                      key={`${a.flight_id}-${idx}`}
                                      variant="outlined"
                                      sx={{ p: 1.2, minWidth: 240 }}
                                    >
                                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                          <IndigoFlightIcon />
                                          <Typography variant="body2" fontWeight="bold">
                                            {a.flight_id}
                                          </Typography>
                                        </Box>
                                        <Chip label={a.aircraft_type} size="small" variant="outlined" />
                                      </Box>
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                                        <Typography variant="caption">
                                          {dayjs(a.dep_dt).format('HH:mm')}
                                        </Typography>
                                        <DottedArrow />
                                        <Typography variant="caption">
                                          {dayjs(a.arr_dt).format('HH:mm')}
                                        </Typography>
                                      </Box>
                                      <Typography variant="caption" display="block">
                                        {a.dep_airport} → {a.arr_airport}
                                      </Typography>
                                      <Chip
                                        label={a.role}
                                        color={getRoleColor(a.role)}
                                        size="small"
                                        sx={{ mt: 0.5 }}
                                      />
                                    </Paper>
                                  ))}
                                </Box>
                              </Paper>
                            ))}
                          </Box>
                        );
                      })()}
                    </>
                  )}

                  {/* All Flight Assignments Summary */}
                  <Typography variant="h6" gutterBottom sx={{ color: '#1A1A1A' }}>
                    All Flight Assignments ({selectedCrew.assignments.length})
                  </Typography>
                  
                  {selectedCrew.assignments.length === 0 ? (
                    <Alert severity="info">
                      No flight assignments for this crew member.
                    </Alert>
                  ) : (
                    <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 300 }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Date</TableCell>
                            <TableCell>Flight</TableCell>
                            <TableCell>Route</TableCell>
                            <TableCell>Departure</TableCell>
                            <TableCell>Duration</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {selectedCrew.assignments
                            .sort((a, b) => new Date(a.dep_dt) - new Date(b.dep_dt))
                            .map((assignment, index) => (
                            <TableRow
                              key={`${assignment.flight_id}-${index}`}
                              sx={{
                                backgroundColor: dayjs(assignment.dep_dt).format('YYYY-MM-DD') === selectedDate.format('YYYY-MM-DD')
                                  ? 'rgba(25, 118, 210, 0.08)'
                                  : 'inherit'
                              }}
                            >
                              <TableCell>
                                <Typography variant="body2" fontWeight="bold">
                                  {dayjs(assignment.dep_dt).format('MMM DD')}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                  <IndigoFlightIcon sx={{ mr: 1 }} />
                                  {assignment.flight_id}
                                </Box>
                              </TableCell>
                              <TableCell>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Typography variant="body2">
                                    {assignment.dep_airport}
                                  </Typography>
                                  <DottedArrow />
                                  <Typography variant="body2">
                                    {assignment.arr_airport}
                                  </Typography>
                                </Box>
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2">
                                  {dayjs(assignment.dep_dt).format('HH:mm')}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                {assignment.duration_min} min
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default CrewWiseView;
