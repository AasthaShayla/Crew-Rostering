import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Grid,
  Paper,
<<<<<<< HEAD
=======
  Button,
>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  PlayArrow,
  Refresh,
  Assessment,
<<<<<<< HEAD
} from '@mui/icons-material';

import OptimizationControl from './OptimizationControl';
import RosterVisualization from './RosterVisualization';
import PostRosterInsights from './PostRosterInsights';
=======
  Schedule,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs from 'dayjs';

import OptimizationControl from './OptimizationControl';
import RosterVisualization from './RosterVisualization';
// import PostRosterInsights from './PostRosterInsights';
>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663

const DashboardView = ({
  currentRoster,
  baselineRoster,
  flights,
  crew,
  loading,
  optimizationProgress,
  onOptimize,
  onReset,
}) => {
  const [selectedDate, setSelectedDate] = useState(null);
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
<<<<<<< HEAD
=======
      {/* Header */}
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Schedule sx={{ mr: 1, color: 'primary.main' }} />
            <Typography variant="h5" sx={{ color: '#1A1A1A', fontWeight: 600 }}>
              Current Roster Overview
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary">
            View and manage your current crew roster assignments and performance metrics.
          </Typography>
          <Box sx={{ mt: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
            <DatePicker
              label="Filter by Date"
              value={selectedDate}
              onChange={(d) => setSelectedDate(d)}
              slotProps={{ textField: { size: 'small', sx: { minWidth: 180 } } }}
            />
            <Button variant="outlined" size="small" onClick={() => setSelectedDate(null)}>
              All Days
            </Button>
          </Box>
        </CardContent>
      </Card>

>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
      {/* Optimization Control Panel */}
      <OptimizationControl
        onOptimize={onOptimize}
        loading={loading}
        hasBaseline={!!baselineRoster}
        onReset={onReset}
      />

      {/* Progress Indicator */}
      {optimizationProgress && optimizationProgress.status === 'running' && (
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <PlayArrow sx={{ mr: 1, color: 'primary.main' }} />
              <Typography variant="h6" sx={{ color: '#1A1A1A' }}>
                Optimization in Progress
              </Typography>
            </Box>
            <LinearProgress 
              variant="determinate" 
              value={optimizationProgress.progress || 0} 
              sx={{ mb: 1 }}
            />
            <Typography variant="body2" color="text.secondary">
              {optimizationProgress.progress || 0}% Complete
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Current Roster Visualization */}
      {currentRoster && (
        <>
          <RosterVisualization
            roster={currentRoster}
            title="Current Roster"
            showKPIs={true}
            controlledDate={selectedDate}
            onChangeDate={setSelectedDate}
          />
<<<<<<< HEAD
          {/* Post-Roster Insights: Standby, Discretion, Overtime */}
          {currentRoster.insights && (
            <Box sx={{ mt: 3 }}>
              <PostRosterInsights insights={currentRoster.insights} />
            </Box>
          )}
=======
          
>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
        </>
      )}

      {/* No Data State */}
      {!currentRoster && !loading && (
        <Card>
          <CardContent>
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Assessment sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No Roster Data Available
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Run an optimization to generate crew assignments and view the roster
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default DashboardView;
