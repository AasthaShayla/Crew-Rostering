import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Button,
  Box,
  Grid,
  TextField,
  Slider,
  FormControl,
  InputLabel,
  CircularProgress,
  Chip,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { PlayArrow, Refresh, Settings, CalendarToday } from '@mui/icons-material';
import dayjs from 'dayjs';

const OptimizationControl = ({ onOptimize, loading, hasBaseline, onReset }) => {
  const [params, setParams] = useState({
    weights: {
      w_ot: 100,
      w_fair: 10,
      w_pref: 1,
      w_base: 50,        // Base return priority
      w_continuity: 75,  // Pilot continuity
    },
    max_time: 30, // Quick optimization for presentations
    start_date: dayjs('2025-09-08'), // Default start date
    end_date: dayjs('2025-09-15'),   // Default to 1 week
  });
  
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleOptimize = () => {
    // Convert dayjs dates to strings for the API
    const apiParams = {
      ...params,
      start_date: params.start_date?.format('YYYY-MM-DD'),
      end_date: params.end_date?.format('YYYY-MM-DD'),
    };
    onOptimize(apiParams);
  };

  const handleWeightChange = (weightType, value) => {
    setParams(prev => ({
      ...prev,
      weights: {
        ...prev.weights,
        [weightType]: value,
      }
    }));
  };

  const resetToDefaults = () => {
    setParams({
      weights: {
        w_ot: 100,
        w_fair: 10,
        w_pref: 1,
        w_base: 50,
        w_continuity: 75,
      },
      max_time: 30, // Quick optimization
      start_date: dayjs('2025-09-08'),
      end_date: dayjs('2025-09-15'),
    });
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <PlayArrow sx={{ mr: 1, color: 'primary.main' }} />
          <Typography variant="h6" component="h2">
            Optimization Control
          </Typography>
          {hasBaseline && (
            <Chip
              label="Baseline Available"
              color="success"
              variant="outlined"
              size="small"
              sx={{ ml: 2 }}
            />
          )}
        </Box>

        <Grid container spacing={3}>
          {/* Date Range Selection */}
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <CalendarToday sx={{ mr: 1, color: 'primary.main' }} />
              <Typography variant="h6" sx={{ color: '#1A1A1A' }}>
                Date Range Selection
              </Typography>
            </Box>
          </Grid>
          
          <Grid item xs={12} md={3}>
            <DatePicker
              label="Start Date"
              value={params.start_date}
              onChange={(date) => setParams(prev => ({ ...prev, start_date: date }))}
              minDate={dayjs('2025-09-08')}
              maxDate={dayjs('2026-03-08')} // 6 months from start
              slotProps={{ textField: { fullWidth: true } }}
            />
          </Grid>
          
          <Grid item xs={12} md={3}>
            <DatePicker
              label="End Date"
              value={params.end_date}
              onChange={(date) => setParams(prev => ({ ...prev, end_date: date }))}
              minDate={params.start_date}
              maxDate={dayjs('2026-03-08')} // 6 months from start
              slotProps={{ textField: { fullWidth: true } }}
            />
          </Grid>

          {/* Max Time */}
          <Grid item xs={12} md={3}>
            <TextField
              label="Max Solve Time (seconds)"
              type="number"
              value={params.max_time}
              onChange={(e) => setParams(prev => ({ ...prev, max_time: parseFloat(e.target.value) }))}
              fullWidth
              inputProps={{ min: 0, max: 3600 }}
              helperText="0 = unlimited"
            />
          </Grid>
          
          {/* Data Info */}
          <Grid item xs={12} md={3}>
            <Box sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 1, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <Typography variant="subtitle2" gutterBottom>
                📊 6-Month Dataset
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • 30 Captains, 30 FOs<br/>
                • 30 Senior Crew, 80 Cabin Crew<br/>
                • ~3,400 flights over 6 months<br/>
                • Full roster optimization
              </Typography>
            </Box>
          </Grid>

          {/* Advanced Settings */}
          {showAdvanced && (
            <>
              <Grid item xs={12}>
                <Typography variant="h6" gutterBottom>
                  Objective Weights
                </Typography>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Adjust the importance of different optimization goals
                </Typography>
              </Grid>

              <Grid item xs={12} md={4}>
                <Typography gutterBottom>
                  Overtime Weight: {params.weights.w_ot}
                </Typography>
                <Slider
                  value={params.weights.w_ot}
                  onChange={(_, value) => handleWeightChange('w_ot', value)}
                  min={0}
                  max={200}
                  valueLabelDisplay="auto"
                  marks={[
                    { value: 0, label: '0' },
                    { value: 100, label: '100' },
                    { value: 200, label: '200' },
                  ]}
                />
                <Typography variant="body2" color="text.secondary">
                  Higher = minimize overtime more aggressively
                </Typography>
              </Grid>

              <Grid item xs={12} md={4}>
                <Typography gutterBottom>
                  Fairness Weight: {params.weights.w_fair}
                </Typography>
                <Slider
                  value={params.weights.w_fair}
                  onChange={(_, value) => handleWeightChange('w_fair', value)}
                  min={0}
                  max={50}
                  valueLabelDisplay="auto"
                  marks={[
                    { value: 0, label: '0' },
                    { value: 10, label: '10' },
                    { value: 50, label: '50' },
                  ]}
                />
                <Typography variant="body2" color="text.secondary">
                  Higher = distribute workload more evenly
                </Typography>
              </Grid>

              <Grid item xs={12} md={4}>
                <Typography gutterBottom>
                  Preference Weight: {params.weights.w_pref}
                </Typography>
                <Slider
                  value={params.weights.w_pref}
                  onChange={(_, value) => handleWeightChange('w_pref', value)}
                  min={0}
                  max={10}
                  valueLabelDisplay="auto"
                  marks={[
                    { value: 0, label: '0' },
                    { value: 1, label: '1' },
                    { value: 10, label: '10' },
                  ]}
                />
                <Typography variant="body2" color="text.secondary">
                  Higher = prioritize crew preferences more
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography gutterBottom>
                  Base Return Weight: {params.weights.w_base}
                </Typography>
                <Slider
                  value={params.weights.w_base}
                  onChange={(_, value) => handleWeightChange('w_base', value)}
                  min={0}
                  max={100}
                  valueLabelDisplay="auto"
                  marks={[
                    { value: 0, label: '0' },
                    { value: 50, label: '50' },
                    { value: 100, label: '100' },
                  ]}
                />
                <Typography variant="body2" color="text.secondary">
                  Higher = prioritize pilots returning to base
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography gutterBottom>
                  Pilot Continuity Weight: {params.weights.w_continuity}
                </Typography>
                <Slider
                  value={params.weights.w_continuity}
                  onChange={(_, value) => handleWeightChange('w_continuity', value)}
                  min={0}
                  max={150}
                  valueLabelDisplay="auto"
                  marks={[
                    { value: 0, label: '0' },
                    { value: 75, label: '75' },
                    { value: 150, label: '150' },
                  ]}
                />
                <Typography variant="body2" color="text.secondary">
                  Higher = enforce pilot continuity more strictly
                </Typography>
              </Grid>
            </>
          )}
        </Grid>
      </CardContent>

      <CardActions sx={{ px: 2, pb: 2 }}>
        <Button
          variant="contained"
          startIcon={loading ? <CircularProgress size={20} /> : <PlayArrow />}
          onClick={handleOptimize}
          disabled={loading}
          size="large"
        >
          {loading ? 'Optimizing...' : 'Run Optimization'}
        </Button>

        <Button
          startIcon={<Settings />}
          onClick={() => setShowAdvanced(!showAdvanced)}
          sx={{ ml: 1 }}
        >
          {showAdvanced ? 'Hide' : 'Show'} Advanced
        </Button>

        <Button
          onClick={resetToDefaults}
          sx={{ ml: 1 }}
        >
          Reset Defaults
        </Button>

        {hasBaseline && (
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={onReset}
            sx={{ ml: 'auto' }}
          >
            Reset to Baseline
          </Button>
        )}
      </CardActions>
    </Card>
  );
};

export default OptimizationControl;