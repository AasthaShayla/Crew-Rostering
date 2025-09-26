import React, { useMemo } from 'react';
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
  Divider,
} from '@mui/material';
import {
  Schedule,
  GroupAdd,
  ReportProblem,
  AccessTime,
  TrendingUp,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';

const roleKey = (raw) => {
  if (!raw) return 'Captain';
  const r = String(raw).trim();
  if (r === 'FO' || r === 'First Officer') return 'FO';
  if (r === 'Cabin Crew' || r === 'CC') return 'CC';
  return 'Captain';
};

const ROLE_COLORS = {
  Captain: '#1976d2',
  FO: '#2e7d32',
  CC: '#f57c00',
};

const PostRosterInsights = ({ insights }) => {
  const overtime = insights?.overtime || {};
  const standby = insights?.standby || {};
  const discretion = insights?.discretion || {};

  const otRows = useMemo(() => {
    const rows = Array.isArray(overtime?.by_crew) ? overtime.by_crew : [];
    return rows
      .map((r) => ({
        crew_id: r.crew_id,
        role: roleKey(r.role),
        assigned_hours: Number(r.assigned_hours || 0),
        weekly_cap_hours: Number(r.weekly_cap_hours || 0),
        overtime_hours: Number(r.overtime_hours || 0),
      }))
      .sort((a, b) => b.overtime_hours - a.overtime_hours);
  }, [overtime?.by_crew]);

  const totalOvertime = Number(overtime?.total_overtime_hours || 0);

  const standbyChartData = useMemo(() => {
    const byDay = Array.isArray(standby?.by_day) ? standby.by_day : [];
    return byDay.map((d) => ({
      day: d.day,
      Captain: d?.peaks?.Captain || 0,
      FO: d?.peaks?.FO || 0,
      CC: d?.peaks?.CC || 0,
      sCaptain: d?.suggested_standby?.Captain || 0,
      sFO: d?.suggested_standby?.FO || 0,
      sCC: d?.suggested_standby?.CC || 0,
    }));
  }, [standby?.by_day]);

  const discretionSummary = useMemo(() => ({
    landing_bracket_excess_events: Number(discretion?.landing_bracket_excess_events || 0),
    wocl_reduction_overcap_events: Number(discretion?.wocl_reduction_overcap_events || 0),
    rest_deficit_events: Number(discretion?.rest_deficit_events || 0),
    approx_extension_hours: Number(discretion?.approx_extension_hours || 0),
    approx_compensatory_rest_hours: Number(discretion?.approx_compensatory_rest_hours || 0),
  }), [discretion]);

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Schedule sx={{ mr: 1, color: 'primary.main' }} />
          <Typography variant="h6" component="h2">
            Post-Roster Insights
          </Typography>
        </Box>

        <Grid container spacing={3}>
          {/* Overtime Breakdown */}
          <Grid item xs={12} md={6}>
            <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <AccessTime sx={{ mr: 1, color: 'warning.main' }} />
                <Typography variant="h6">Overtime Breakdown</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Weekly overtime computed against each crew member's cap after optimization.
              </Typography>

              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2" fontWeight="bold">
                  Total Overtime:
                </Typography>
                <Chip
                  label={`${totalOvertime.toFixed(2)} h`}
                  color={totalOvertime > 0 ? 'warning' : 'success'}
                  size="small"
                />
              </Box>

              <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 360 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell>Crew</TableCell>
                      <TableCell>Role</TableCell>
                      <TableCell align="right">Assigned (h)</TableCell>
                      <TableCell align="right">Cap (h)</TableCell>
                      <TableCell align="right">Overtime (h)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {otRows.map((r) => (
                      <TableRow key={r.crew_id} hover>
                        <TableCell>{r.crew_id}</TableCell>
                        <TableCell>
                          <Chip
                            label={r.role}
                            size="small"
                            sx={{ bgcolor: '#fafafa', border: `1px solid ${ROLE_COLORS[r.role]}`, color: ROLE_COLORS[r.role] }}
                          />
                        </TableCell>
                        <TableCell align="right">{r.assigned_hours.toFixed(2)}</TableCell>
                        <TableCell align="right">{r.weekly_cap_hours.toFixed(2)}</TableCell>
                        <TableCell align="right">
                          <Chip
                            label={r.overtime_hours.toFixed(2)}
                            size="small"
                            color={r.overtime_hours > 0 ? 'warning' : 'success'}
                            variant={r.overtime_hours > 0 ? 'filled' : 'outlined'}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                    {otRows.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5} align="center">
                          <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                            No overtime detected
                          </Typography>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>

          {/* Standby Recommendations */}
          <Grid item xs={12} md={6}>
            <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <GroupAdd sx={{ mr: 1, color: 'info.main' }} />
                <Typography variant="h6">Standby Recommendations</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Suggested standby per day based on peak hourly seat requirements (±10% rule of thumb).
              </Typography>

              <Box sx={{ height: 280 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={standbyChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" />
                    <YAxis />
                    <RechartsTooltip />
                    <Bar dataKey="Captain" stackId="req" fill="#1976d2" name="Captain Peak" />
                    <Bar dataKey="FO" stackId="req" fill="#2e7d32" name="FO Peak" />
                    <Bar dataKey="CC" stackId="req" fill="#f57c00" name="CC Peak" />
                  </BarChart>
                </ResponsiveContainer>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
                <TrendingUp fontSize="small" sx={{ color: 'secondary.main' }} />
                <Typography variant="subtitle2">Suggested Standby (per day)</Typography>
              </Box>

              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {standby?.by_day?.map((d) => (
                  <Paper key={d.day} variant="outlined" sx={{ p: 1.2 }}>
                    <Typography variant="caption" sx={{ display: 'block', fontWeight: 600 }}>
                      {new Date(d.day).toLocaleDateString()}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                      <Chip size="small" label={`CPT ${d.suggested_standby?.Captain || 0}`} />
                      <Chip size="small" label={`FO ${d.suggested_standby?.FO || 0}`} />
                      <Chip size="small" label={`CC ${d.suggested_standby?.CC || 0}`} />
                    </Box>
                  </Paper>
                ))}
                {!standby?.by_day?.length && (
                  <Typography variant="body2" color="text.secondary">
                    No standby suggestions available
                  </Typography>
                )}
              </Box>
            </Paper>
          </Grid>

          {/* Discretion / Unforeseen Extensions */}
          <Grid item xs={12}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <ReportProblem sx={{ mr: 1, color: 'error.main' }} />
                <Typography variant="h6">Unforeseen Situations (Discretion) Indicators</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Counts are approximations derived from FDP landing brackets, WOCL reductions, and rest gaps.
                Use these as flags to review duty periods that may need additional oversight or compensatory rest.
              </Typography>

              <Grid container spacing={2}>
                <Grid item xs={12} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }} variant="outlined">
                    <Typography variant="h4" color="warning.main">
                      {discretionSummary.landing_bracket_excess_events}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Landing-Bracket Excess Events
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }} variant="outlined">
                    <Typography variant="h4" color="warning.main">
                      {discretionSummary.wocl_reduction_overcap_events}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      WOCL Reduction Over-Cap Events
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }} variant="outlined">
                    <Typography variant="h4" color="warning.main">
                      {discretionSummary.rest_deficit_events}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Rest Deficit Events
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }} variant="outlined">
                    <Typography variant="h4" color="error.main">
                      {discretionSummary.approx_extension_hours.toFixed(2)}h
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Approx. Extension Hours
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>

              <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
                <Chip
                  label={`Approx. Compensatory Rest: ${discretionSummary.approx_compensatory_rest_hours.toFixed(2)} h`}
                  color="info"
                  variant="outlined"
                />
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default PostRosterInsights;