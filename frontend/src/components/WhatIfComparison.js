import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Grid,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
  Divider,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  ExpandMore,
  CompareArrows,
  TrendingUp,
  TrendingDown,
  SwapHoriz,
  PersonAdd,
  PersonRemove,
  FlightTakeoff,
  Assessment,
  Visibility,
  VisibilityOff,
} from '@mui/icons-material';

const WhatIfComparison = ({ beforeRoster, afterRoster, changes }) => {
  const [showDetails, setShowDetails] = useState(true);
  const [viewMode, setViewMode] = useState('summary'); // 'summary' or 'detailed'

  if (!beforeRoster || !afterRoster || !changes) {
    return (
      <Alert severity="info">
        Run a what-if scenario to see comparison results
      </Alert>
    );
  }

  const { summary, crew_changes } = changes;
  
  // Calculate KPI differences
  const kpiDiff = {
    coverage: (afterRoster.kpis?.coverage_pct || 0) - (beforeRoster.kpis?.coverage_pct || 0),
    avg_hours: (afterRoster.kpis?.avg_hours || 0) - (beforeRoster.kpis?.avg_hours || 0),
    overtime: (afterRoster.kpis?.total_overtime_hours || 0) - (beforeRoster.kpis?.total_overtime_hours || 0),
  };

  const renderKPIDiff = (label, value, unit = '%', format = 'percentage') => {
    const isPositive = value > 0;
    const isNegative = value < 0;
    const color = format === 'overtime' 
      ? (isPositive ? 'error' : 'success') // For overtime, less is better
      : (isPositive ? 'success' : isNegative ? 'error' : 'default');
    
    const icon = isPositive ? <TrendingUp /> : isNegative ? <TrendingDown /> : <SwapHoriz />;
    
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="body2" fontWeight="bold">
          {label}:
        </Typography>
        <Chip
          icon={icon}
          label={`${value >= 0 ? '+' : ''}${value.toFixed(2)}${unit}`}
          color={color}
          size="small"
          variant={value === 0 ? 'outlined' : 'filled'}
        />
      </Box>
    );
  };

  const renderChangesByType = (type) => {
    const typeChanges = crew_changes.filter(change => change.type === type);
    if (typeChanges.length === 0) return null;

    return (
      <List dense>
        {typeChanges.map((change, index) => (
          <ListItem key={index} sx={{ py: 0.5 }}>
            <ListItemIcon sx={{ minWidth: 32 }}>
              {type === 'added' ? (
                <PersonAdd color="success" fontSize="small" />
              ) : (
                <PersonRemove color="error" fontSize="small" />
              )}
            </ListItemIcon>
            <ListItemText
              primary={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="body2" fontWeight="bold">
                    {change.crew_id}
                  </Typography>
                  <Chip label={change.role} size="small" variant="outlined" />
                </Box>
              }
              secondary={
                <Typography variant="body2" color="text.secondary">
                  Flight {change.flight_id}: {change.flight_details}
                </Typography>
              }
            />
          </ListItem>
        ))}
      </List>
    );
  };

  const renderDetailedComparison = () => {
    const beforeAssignments = beforeRoster.assignments || [];
    const afterAssignments = afterRoster.assignments || [];
    
    // Group assignments by crew
    const groupByCrewId = (assignments) => {
      return assignments.reduce((acc, assignment) => {
        if (!acc[assignment.crew_id]) {
          acc[assignment.crew_id] = [];
        }
        acc[assignment.crew_id].push(assignment);
        return acc;
      }, {});
    };

    const beforeByCrew = groupByCrewId(beforeAssignments);
    const afterByCrew = groupByCrewId(afterAssignments);
    
    // Get all crew IDs that had changes
    const changedCrewIds = new Set(crew_changes.map(change => change.crew_id));
    
    return (
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Crew ID</TableCell>
              <TableCell align="center">Baseline Flights</TableCell>
              <TableCell align="center">New Scenario Flights</TableCell>
              <TableCell align="center">Change</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {Array.from(changedCrewIds).map(crewId => {
              const beforeFlights = (beforeByCrew[crewId] || []).length;
              const afterFlights = (afterByCrew[crewId] || []).length;
              const diff = afterFlights - beforeFlights;
              
              return (
                <TableRow key={crewId} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight="bold">
                      {crewId}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">{beforeFlights}</TableCell>
                  <TableCell align="center">{afterFlights}</TableCell>
                  <TableCell align="center">
                    <Chip
                      label={`${diff >= 0 ? '+' : ''}${diff}`}
                      color={diff > 0 ? 'success' : diff < 0 ? 'error' : 'default'}
                      size="small"
                      variant={diff === 0 ? 'outlined' : 'filled'}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
            {changedCrewIds.size === 0 && (
              <TableRow>
                <TableCell colSpan={4} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                    No crew assignment changes detected
                  </Typography>
                </TableCell>
              </TableRow>
            )}
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
            <CompareArrows sx={{ mr: 1, color: 'info.main' }} />
            <Typography variant="h6" component="h2">
              What-If Scenario Results
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title={showDetails ? 'Hide Details' : 'Show Details'}>
              <IconButton
                onClick={() => setShowDetails(!showDetails)}
                size="small"
              >
                {showDetails ? <VisibilityOff /> : <Visibility />}
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Impact Summary */}
        <Alert severity="info" sx={{ mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Scenario Impact Summary
          </Typography>
          <Typography variant="body2">
            {summary.total_changes} crew assignment changes detected. 
            Coverage changed from {summary.coverage_before?.toFixed(1)}% to {summary.coverage_after?.toFixed(1)}%.
          </Typography>
        </Alert>

        <Grid container spacing={3}>
          {/* KPI Comparison */}
          <Grid item xs={12} md={6}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                <Assessment sx={{ mr: 1 }} />
                Performance Impact
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                {renderKPIDiff('Coverage', kpiDiff.coverage)}
                {renderKPIDiff('Avg Hours', kpiDiff.avg_hours, 'h', 'hours')}
                {renderKPIDiff('Total Overtime', kpiDiff.overtime, 'h', 'overtime')}
              </Box>
            </Paper>
          </Grid>

          {/* Change Summary */}
          <Grid item xs={12} md={6}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                <FlightTakeoff sx={{ mr: 1 }} />
                Assignment Changes
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Assignments Removed:</Typography>
                  <Chip label={summary.assignments_removed || 0} color="error" size="small" />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Assignments Added:</Typography>
                  <Chip label={summary.assignments_added || 0} color="success" size="small" />
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Net Change:</Typography>
                  <Chip 
                    label={(summary.assignments_added || 0) - (summary.assignments_removed || 0)} 
                    color="info" 
                    size="small" 
                  />
                </Box>
              </Box>
            </Paper>
          </Grid>
        </Grid>

        {showDetails && (
          <>
            <Divider sx={{ my: 3 }} />
            
            <Grid container spacing={3}>
              {/* Detailed Changes */}
              <Grid item xs={12} md={6}>
                <Accordion defaultExpanded>
                  <AccordionSummary expandIcon={<ExpandMore />}>
                    <Typography variant="h6">
                      Removed Assignments ({summary.assignments_removed || 0})
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    {renderChangesByType('removed')}
                    {(summary.assignments_removed || 0) === 0 && (
                      <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                        No assignments were removed
                      </Typography>
                    )}
                  </AccordionDetails>
                </Accordion>
              </Grid>

              <Grid item xs={12} md={6}>
                <Accordion defaultExpanded>
                  <AccordionSummary expandIcon={<ExpandMore />}>
                    <Typography variant="h6">
                      Added Assignments ({summary.assignments_added || 0})
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    {renderChangesByType('added')}
                    {(summary.assignments_added || 0) === 0 && (
                      <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                        No new assignments were added
                      </Typography>
                    )}
                  </AccordionDetails>
                </Accordion>
              </Grid>

              {/* Crew Impact Table */}
              <Grid item xs={12}>
                <Accordion>
                  <AccordionSummary expandIcon={<ExpandMore />}>
                    <Typography variant="h6">
                      Crew Impact Analysis
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    {renderDetailedComparison()}
                  </AccordionDetails>
                </Accordion>
              </Grid>
            </Grid>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default WhatIfComparison;