import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  CircularProgress,
  Paper,
  Button,
  Divider,
  Tooltip,
} from '@mui/material';
import {
  ArrowBack,
  ArrowForward,
  Cloud,
  Warning as WarningIcon,
} from '@mui/icons-material';
import dayjs from 'dayjs';
import { apiService } from '../services/api';

function startOfMonth(d) {
  return dayjs(d).startOf('month');
}
function endOfMonth(d) {
  return dayjs(d).endOf('month');
}
function toISODate(d) {
  return dayjs(d).format('YYYY-MM-DD');
}
function buildCalendarMatrix(monthDate) {
  const start = startOfMonth(monthDate);
  const end = endOfMonth(monthDate);
  const startDay = start.day(); // 0=Sun .. 6=Sat

  // We build 6 weeks x 7 days = 42 boxes
  const cells = [];
  // Date of the first cell is the Sunday of the first week
  const firstCellDate = start.subtract(startDay, 'day');

  for (let i = 0; i < 42; i++) {
    const cellDate = firstCellDate.add(i, 'day');
    const inMonth = cellDate.month() === start.month();
    cells.push({
      date: cellDate,
      inMonth,
      iso: toISODate(cellDate),
      isToday: toISODate(cellDate) === toISODate(dayjs()),
    });
  }

  // Split into weeks
  const weeks = [];
  for (let w = 0; w < 6; w++) {
    weeks.push(cells.slice(w * 7, w * 7 + 7));
  }
  return weeks;
}

const DayBadge = ({ count }) => {
  if (!count || count <= 0) return null;
  return (
    <Chip
      label={`${count}`}
      size="small"
      color="error"
      sx={{
        position: 'absolute',
        top: 6,
        right: 6,
        height: 20,
        '& .MuiChip-label': { px: 0.75, fontSize: 12 },
      }}
    />
  );
};

const RiskChip = ({ level, minutes }) => {
  const color =
    level === 'high' ? 'error' : level === 'medium' ? 'warning' : 'default';
  return (
    <Chip
      icon={level === 'high' ? <WarningIcon sx={{ fontSize: 18 }} /> : <Cloud sx={{ fontSize: 18 }} />}
      label={`${(level || 'none').toUpperCase()}${minutes ? ` · ${minutes}m` : ''}`}
      size="small"
      color={color}
      variant={level === 'low' || level === 'none' ? 'outlined' : 'filled'}
      sx={{ mr: 1, mb: 1 }}
    />
  );
};

const WeatherCalendarView = () => {
  const [month, setMonth] = useState(dayjs().startOf('month'));
  const [summary, setSummary] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [summaryError, setSummaryError] = useState('');

  const [selectedDate, setSelectedDate] = useState(null);
  const [details, setDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [detailsError, setDetailsError] = useState('');

  const start = useMemo(() => toISODate(startOfMonth(month)), [month]);
  const end = useMemo(() => toISODate(endOfMonth(month)), [month]);

  useEffect(() => {
    let alive = true;
    async function load() {
      setLoadingSummary(true);
      setSummaryError('');
      try {
        const res = await apiService.weatherSummary(start, end);
        if (!alive) return;
        setSummary(res.data);
      } catch (e) {
        if (!alive) return;
        setSummaryError(e?.message || 'Failed to load weather summary');
      } finally {
        if (alive) setLoadingSummary(false);
      }
    }
    load();
    return () => {
      alive = false;
    };
  }, [start, end]);

  const daysMap = useMemo(() => {
    const m = {};
    if (summary?.days) {
      summary.days.forEach((d) => {
        m[d.date] = d;
      });
    }
    return m;
  }, [summary]);

  const weeks = useMemo(() => buildCalendarMatrix(month), [month]);

  async function onSelectDay(iso) {
    setSelectedDate(iso);
    setDetails(null);
    setDetailsError('');
    setLoadingDetails(true);
    try {
      const res = await apiService.weatherDay(iso);
      setDetails(res.data);
    } catch (e) {
      setDetailsError(e?.message || 'Failed to load day details');
    } finally {
      setLoadingDetails(false);
    }
  }

  function goPrevMonth() {
    setMonth((m) => m.subtract(1, 'month'));
  }
  function goNextMonth() {
    setMonth((m) => m.add(1, 'month'));
  }

  const weekdayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Cloud sx={{ color: 'primary.main' }} />
              <Typography variant="h5" sx={{ color: '#1A1A1A', fontWeight: 600 }}>
                Weather Forecast Impact Calendar
              </Typography>
            </Box>
            <Box>
              <Button onClick={goPrevMonth} startIcon={<ArrowBack />} sx={{ mr: 1 }} variant="outlined" size="small">
                Prev
              </Button>
              <Button onClick={goNextMonth} endIcon={<ArrowForward />} variant="outlined" size="small">
                Next
              </Button>
            </Box>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Dates marked in red indicate predicted weather impacts (medium/high) potentially causing delays.
          </Typography>

          <Grid container spacing={3}>
            <Grid item xs={12} md={7} lg={8}>
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="h6" sx={{ color: '#1A1A1A' }}>
                    {month.format('MMMM YYYY')}
                  </Typography>
                  {loadingSummary && <CircularProgress size={18} />}
                </Box>

                {summaryError ? (
                  <Typography color="error">{summaryError}</Typography>
                ) : (
                  <Box>
                    {/* Weekday header */}
                    <Grid container spacing={0.5} sx={{ mb: 0.5 }} columns={7}>
                      {weekdayLabels.map((d) => (
                        <Grid item xs={1} key={d} sx={{ flexBasis: '14.2857%', maxWidth: '14.2857%' }}>
                          <Box sx={{ textAlign: 'center', color: 'text.secondary', fontSize: 12, fontWeight: 600 }}>
                            {d}
                          </Box>
                        </Grid>
                      ))}
                    </Grid>

                    {/* Calendar weeks */}
                    {weeks.map((week, wi) => (
                      <Grid container spacing={0.75} key={wi} sx={{ mb: 0.5 }} columns={7}>
                        {week.map((cell) => {
                          const s = daysMap[cell.iso];
                          const affected = s?.affected_flights || 0;
                          const isDisabled = !cell.inMonth;
                          const red = affected > 0 && cell.inMonth;

                          return (
                            <Grid
                              item
                              key={cell.iso}
                              xs={1}
                              sx={{
                                flexBasis: '14.2857%',
                                maxWidth: '14.2857%',
                                opacity: isDisabled ? 0.35 : 1,
                              }}
                            >
                              <Tooltip
                                title={
                                  red
                                    ? `${affected} flight${affected !== 1 ? 's' : ''} potentially impacted`
                                    : cell.inMonth
                                      ? 'No predicted impacts'
                                      : ''
                                }
                                arrow
                              >
                                <Box
                                  onClick={() => cell.inMonth && onSelectDay(cell.iso)}
                                  sx={{
                                    position: 'relative',
                                    height: 88,
                                    borderRadius: 1.25,
                                    border: '1px solid',
                                    borderColor: red ? 'error.light' : 'divider',
                                    bgcolor: red ? 'error.50' : '#fff',
                                    cursor: cell.inMonth ? 'pointer' : 'default',
                                    p: 1,
                                    '&:hover': cell.inMonth
                                      ? { boxShadow: 2, borderColor: red ? 'error.main' : 'primary.light' }
                                      : {},
                                    display: 'flex',
                                    flexDirection: 'column',
                                  }}
                                >
                                  <Typography
                                    variant="body2"
                                    sx={{
                                      fontWeight: cell.isToday ? 700 : 500,
                                      color: cell.isToday ? 'primary.main' : '#1A1A1A',
                                    }}
                                  >
                                    {dayjs(cell.date).date()}
                                  </Typography>

                                  <Box sx={{ flexGrow: 1 }} />

                                  {red ? (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                      <WarningIcon sx={{ fontSize: 16, color: 'error.main' }} />
                                      <Typography variant="caption" sx={{ color: 'error.main', fontWeight: 600 }}>
                                        {affected} flagged
                                      </Typography>
                                    </Box>
                                  ) : (
                                    <Typography variant="caption" color="text.secondary">—</Typography>
                                  )}

                                  <DayBadge count={affected} />
                                </Box>
                              </Tooltip>
                            </Grid>
                          );
                        })}
                      </Grid>
                    ))}
                  </Box>
                )}
              </Paper>
            </Grid>

            <Grid item xs={12} md={5} lg={4}>
              <Paper variant="outlined" sx={{ p: 2, minHeight: 420 }}>
                <Typography variant="h6" gutterBottom sx={{ color: '#1A1A1A' }}>
                  {selectedDate ? `Forecast Details · ${dayjs(selectedDate).format('DD MMM YYYY')}` : 'Forecast Details'}
                </Typography>

                {!selectedDate && (
                  <Typography variant="body2" color="text.secondary">
                    Select a red date to view potentially impacted flights and high-risk airports.
                  </Typography>
                )}

                {selectedDate && loadingDetails && (
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
                    <CircularProgress size={24} />
                  </Box>
                )}

                {selectedDate && detailsError && (
                  <Typography color="error">{detailsError}</Typography>
                )}

                {selectedDate && !loadingDetails && details && details.success && (
                  <Box>
                    {/* Airports risk */}
                    <Typography variant="subtitle2" sx={{ mb: 1.25 }}>Airports (risk)</Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 2 }}>
                      {(details.airports || []).map((ap) => (
                        <Chip
                          key={ap.airport}
                          label={`${ap.airport}: ${ap.risk_level.toUpperCase()} · P${ap.precip_probability_max}% · W${Math.round(ap.wind_speed_10m_max)}km/h`}
                          color={ap.risk_level === 'high' ? 'error' : ap.risk_level === 'medium' ? 'warning' : 'default'}
                          variant={ap.risk_level === 'low' || ap.risk_level === 'none' ? 'outlined' : 'filled'}
                          size="small"
                        />
                      ))}
                    </Box>

                    <Divider sx={{ mb: 1.5 }} />

                    {/* Flights list */}
                    <Typography variant="subtitle2" sx={{ mb: 1.25 }}>Affected Flights</Typography>
                    {(details.affected_flights || []).length === 0 ? (
                      <Typography variant="body2" color="text.secondary">No flights predicted to be impacted on this date.</Typography>
                    ) : (
                      <Box sx={{ maxHeight: 320, overflow: 'auto' }}>
                        {(details.affected_flights || []).map((f) => (
                          <Paper key={f.flight_id + f.dep_dt} variant="outlined" sx={{ p: 1.25, mb: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                              <Box>
                                <Typography variant="subtitle2" sx={{ color: '#003DA5', fontWeight: 700 }}>
                                  {f.flight_id}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                  {f.dep_airport} → {f.arr_airport}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {new Date(f.dep_dt).toLocaleString()}
                                </Typography>
                              </Box>
                              <Box>
                                <RiskChip level={f.risk_level} minutes={f.predicted_delay_minutes} />
                              </Box>
                            </Box>
                            {f.reason && (
                              <Typography variant="caption" color="text.secondary">{f.reason}</Typography>
                            )}
                          </Paper>
                        ))}
                      </Box>
                    )}
                  </Box>
                )}
              </Paper>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Typography variant="body2" color="text.secondary">
        Powered by Open-Meteo (no API key). When unavailable, a deterministic fallback generates pseudo-risk to
        keep UX consistent. Summary by date fetched via backend endpoints.
      </Typography>
    </Box>
  );
};

export default WeatherCalendarView;