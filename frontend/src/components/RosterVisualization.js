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
  Tabs,
  Tab,
  Tooltip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
} from '@mui/material';
import {
  Schedule,
  Assessment,
  Person,
  ViewTimeline,
  TableChart,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs from 'dayjs';

const ROLE_COLORS = {
  Captain: '#1976d2',
  FO: '#2e7d32',
  SC: '#9c27b0',
  CC: '#f57c00',
};

const AIRCRAFT_COLORS = {
  A320: '#e3f2fd',
  A321: '#e8f5e8',
  ATR72: '#fff3e0',
};

const roleKey = (raw) => {
  if (!raw) return 'Captain';
  const r = String(raw).trim();
  if (r === 'FO' || r === 'First Officer') return 'FO';
  if (r === 'Senior Crew' || r === 'SC') return 'SC';
  if (r === 'Cabin Crew' || r === 'CC') return 'CC';
  return 'Captain';
};

const RosterVisualization = ({ roster, title = "Roster Visualization", showKPIs = true, controlledDate = null, onChangeDate }) => {
  const [activeTab, setActiveTab] = useState(0);
  const [internalDate, setInternalDate] = useState(null);
  const selectedDate = controlledDate ?? internalDate;
  const [selectedRole, setSelectedRole] = useState('all');

  // Extract data safely with memoization to prevent dependency issues
  const assignments = useMemo(() => roster?.assignments || [], [roster?.assignments]);
  const kpis = useMemo(() => roster?.kpis || null, [roster?.kpis]);
  const operating_days = useMemo(() => roster?.operating_days || [], [roster?.operating_days]);

  // Process data for visualizations - this hook must be called before any early returns
  const processedData = useMemo(() => {
    if (!assignments.length) {
      return {
        byCrewAndDay: [],
        byDay: [],
        byRole: [],
        byAircraft: [],
      };
    }

    // Group assignments by crew and day
    const byCrewAndDay = {};
    const byDay = {};
    const byRole = {};
    const byAircraft = {};

    assignments.forEach(assignment => {
      const day = assignment.dep_dt.split('T')[0];
      const crewKey = `${assignment.crew_id}`;
      const dayKey = `${crewKey}-${day}`;

      // By crew and day
      if (!byCrewAndDay[dayKey]) {
        byCrewAndDay[dayKey] = {
          crew_id: assignment.crew_id,
          role: assignment.role,
          day,
          flights: [],
          total_minutes: 0,
        };
      }
      byCrewAndDay[dayKey].flights.push(assignment);
      byCrewAndDay[dayKey].total_minutes += assignment.duration_min;

      // By day
      if (!byDay[day]) {
        byDay[day] = { day, flights: 0, crew_assigned: 0 };
      }
      byDay[day].flights++;

      // By role (normalize role labels)
      const rk = roleKey(assignment.role);
      if (!byRole[rk]) {
        byRole[rk] = 0;
      }
      byRole[rk]++;

      // By aircraft
      if (!byAircraft[assignment.aircraft_type]) {
        byAircraft[assignment.aircraft_type] = 0;
      }
      byAircraft[assignment.aircraft_type]++;
    });

    // Calculate unique crew per day
    Object.keys(byDay).forEach(day => {
      const crewOnDay = new Set(
        assignments
          .filter(a => a.dep_dt.split('T')[0] === day)
          .map(a => a.crew_id)
      );
      byDay[day].crew_assigned = crewOnDay.size;
    });

    return {
      byCrewAndDay: Object.values(byCrewAndDay),
      byDay: Object.values(byDay).sort((a, b) => a.day.localeCompare(b.day)),
      byRole: Object.entries(byRole).map(([role, count]) => ({ role, count })),
      byAircraft: Object.entries(byAircraft).map(([aircraft, count]) => ({ aircraft, count })),
    };
  }, [assignments]);

  // Filter data based on selections - this hook must also be called before any early returns
  const filteredAssignments = useMemo(() => {
    if (!assignments.length) {
      return [];
    }
    return assignments.filter(assignment => {
      const day = assignment.dep_dt.split('T')[0];
      const dayMatch = !selectedDate || day === dayjs(selectedDate).format('YYYY-MM-DD');
      const roleMatch = selectedRole === 'all' || roleKey(assignment.role) === roleKey(selectedRole);
      return dayMatch && roleMatch;
    });
  }, [assignments, selectedDate, selectedRole]);

  // Early return AFTER all hooks have been called
  if (!roster || !roster.assignments) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" color="text.secondary" align="center" sx={{ py: 4 }}>
            No roster data available
          </Typography>
        </CardContent>
      </Card>
    );
  }

  const renderKPIs = () => {
    if (!showKPIs || !kpis) return null;

    return (
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="primary">
              {kpis.coverage_pct?.toFixed(1) || 0}%
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Schedule Coverage
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="success.main">
              {kpis.avg_hours?.toFixed(1) || 0}h
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Avg Crew Hours
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="warning.main">
              {kpis.total_overtime_hours?.toFixed(1) || 0}h
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Overtime
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="info.main">
              {assignments.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Assignments
            </Typography>
          </Paper>
        </Grid>
      </Grid>
    );
  };

  const renderTimelineView = () => {
    // Group assignments by crew for timeline view
    const crewTimelines = {};
    filteredAssignments.forEach(assignment => {
      if (!crewTimelines[assignment.crew_id]) {
        crewTimelines[assignment.crew_id] = {
          crew_id: assignment.crew_id,
          role: assignment.role,
          assignments: [],
        };
      }
      crewTimelines[assignment.crew_id].assignments.push(assignment);
    });

    // Sort assignments by time for each crew
    Object.values(crewTimelines).forEach(crew => {
      crew.assignments.sort((a, b) => new Date(a.dep_dt) - new Date(b.dep_dt));
    });

    return (
      <Box>
        {Object.values(crewTimelines).map(crew => (
          <Paper key={crew.crew_id} sx={{ mb: 2, p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Person sx={{ mr: 1, color: ROLE_COLORS[roleKey(crew.role)] }} />
              <Typography variant="h6">
                {crew.crew_id}
              </Typography>
              <Chip label={crew.role} color="primary" size="small" sx={{ ml: 1 }} />
              <Typography variant="body2" color="text.secondary" sx={{ ml: 2 }}>
                {crew.assignments.length} flight{crew.assignments.length !== 1 ? 's' : ''}
              </Typography>
            </Box>
            
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {crew.assignments.map((assignment, index) => {
                const startTime = new Date(assignment.dep_dt);
                const endTime = new Date(assignment.arr_dt);
                const duration = assignment.duration_min;
                
                return (
                  <Tooltip
                    key={`${assignment.flight_id}-${index}`}
                    title={
                      <Box>
                        <Typography variant="subtitle2">
                          Flight {assignment.flight_id}
                        </Typography>
                        <Typography variant="body2">
                          {assignment.dep_airport} → {assignment.arr_airport}
                        </Typography>
                        <Typography variant="body2">
                          {startTime.toLocaleTimeString()} - {endTime.toLocaleTimeString()}
                        </Typography>
                        <Typography variant="body2">
                          Duration: {duration} minutes
                        </Typography>
                        <Typography variant="body2">
                          Aircraft: {assignment.aircraft_type}
                        </Typography>
                      </Box>
                    }
                  >
                    <Paper
                      sx={{
                        p: 1,
                        minWidth: `${Math.max(80, duration / 2)}px`,
                        bgcolor: AIRCRAFT_COLORS[assignment.aircraft_type] || '#f5f5f5',
                        border: `2px solid ${ROLE_COLORS[roleKey(assignment.role)]}`,
                        cursor: 'pointer',
                        '&:hover': {
                          opacity: 0.8,
                        },
                      }}
                    >
                      <Typography variant="caption" fontWeight="bold">
                        {assignment.flight_id}
                      </Typography>
                      <Typography variant="caption" display="block">
                        {assignment.dep_airport}→{assignment.arr_airport}
                      </Typography>
                      <Typography variant="caption" display="block">
                        {startTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </Typography>
                    </Paper>
                  </Tooltip>
                );
              })}
            </Box>
          </Paper>
        ))}
        
        {Object.keys(crewTimelines).length === 0 && (
          <Typography variant="body1" color="text.secondary" align="center" sx={{ py: 4 }}>
            No assignments found for the selected filters
          </Typography>
        )}
      </Box>
    );
  };

  const renderChartsView = () => {
    return (
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Daily Operations
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={processedData.byDay}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" />
                <YAxis />
                <RechartsTooltip />
                <Bar dataKey="flights" fill="#1976d2" name="Flights" />
                <Bar dataKey="crew_assigned" fill="#2e7d32" name="Crew Assigned" />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Role Distribution
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={processedData.byRole}
                  dataKey="count"
                  nameKey="role"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label
                >
                  {processedData.byRole.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={ROLE_COLORS[entry.role] || '#8884d8'} />
                  ))}
                </Pie>
                <RechartsTooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Aircraft Utilization
            </Typography>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={processedData.byAircraft} layout="horizontal">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="aircraft" type="category" />
                <RechartsTooltip />
                <Bar dataKey="count" fill="#ff6b35" />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>
      </Grid>
    );
  };

  const renderTableView = () => {
    return (
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Crew ID</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Flight ID</TableCell>
              <TableCell>Route</TableCell>
              <TableCell>Departure</TableCell>
              <TableCell>Arrival</TableCell>
              <TableCell>Aircraft</TableCell>
              <TableCell align="right">Duration</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredAssignments
              .sort((a, b) => new Date(a.dep_dt) - new Date(b.dep_dt))
              .map((assignment, index) => (
                <TableRow key={`${assignment.crew_id}-${assignment.flight_id}-${index}`} hover>
                  <TableCell>{assignment.crew_id}</TableCell>
                  <TableCell>
                    <Chip 
                      label={assignment.role} 
                      color="primary" 
                      size="small" 
                    />
                  </TableCell>
                  <TableCell>{assignment.flight_id}</TableCell>
                  <TableCell>
                    {assignment.dep_airport} → {assignment.arr_airport}
                  </TableCell>
                  <TableCell>
                    {new Date(assignment.dep_dt).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    {new Date(assignment.arr_dt).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={assignment.aircraft_type} 
                      variant="outlined" 
                      size="small" 
                    />
                  </TableCell>
                  <TableCell align="right">
                    {assignment.duration_min} min
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Schedule sx={{ mr: 1, color: 'primary.main' }} />
            <Typography variant="h6" component="h2">
              {title}
            </Typography>
          </Box>
          
          {/* Filters */}
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <DatePicker
              label="Select Date"
              value={selectedDate}
              onChange={(d) => (onChangeDate ? onChangeDate(d) : setInternalDate(d))}
              slotProps={{ textField: { size: 'small', sx: { minWidth: 180 } } }}
            />
            <Button
              variant="outlined"
              size="small"
              onClick={() => (onChangeDate ? onChangeDate(null) : setInternalDate(null))}
            >
              All Days
            </Button>

            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel>Role</InputLabel>
              <Select
                value={selectedRole}
                onChange={(e) => setSelectedRole(e.target.value)}
                label="Role"
              >
                <MenuItem value="all">All Roles</MenuItem>
                <MenuItem value="Captain">Captain</MenuItem>
                <MenuItem value="First Officer">First Officer</MenuItem>
                <MenuItem value="Senior Crew">Senior Crew</MenuItem>
                <MenuItem value="Cabin Crew">Cabin Crew</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Box>

        {renderKPIs()}

        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
            <Tab icon={<ViewTimeline />} label="Timeline" />
            <Tab icon={<Assessment />} label="Charts" />
            <Tab icon={<TableChart />} label="Table" />
          </Tabs>
        </Box>

        <Box>
          {activeTab === 0 && renderTimelineView()}
          {activeTab === 1 && renderChartsView()}
          {activeTab === 2 && renderTableView()}
        </Box>
      </CardContent>
    </Card>
  );
};

export default RosterVisualization;