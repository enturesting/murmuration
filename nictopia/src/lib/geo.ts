import type { ISO, NodeId } from '../types';

export const DC_LOCATIONS: Record<
  Extract<NodeId, 'dc-caiso' | 'dc-ercot' | 'dc-pjm'>,
  { lat: number; lng: number; ba: ISO; metro: string }
> = {
  'dc-caiso': { lat: 37.74, lng: -121.43, ba: 'CAISO', metro: 'Tracy / CA-North' },
  'dc-ercot': { lat: 32.78, lng: -96.80, ba: 'ERCOT', metro: 'Dallas / TX-1' },
  'dc-pjm': { lat: 39.04, lng: -77.49, ba: 'PJM', metro: 'Ashburn / NoVA' },
};

export const BA_CENTERS: { ba: ISO; lat: number; lng: number }[] = [
  { ba: 'CAISO', lat: 36.8, lng: -119.7 },
  { ba: 'ERCOT', lat: 31.0, lng: -99.0 },
  { ba: 'PJM', lat: 39.5, lng: -77.0 },
  { ba: 'MISO', lat: 41.5, lng: -91.5 },
  { ba: 'NYISO', lat: 42.7, lng: -75.0 },
  { ba: 'ISO-NE', lat: 43.5, lng: -71.5 },
  { ba: 'SPP', lat: 38.5, lng: -98.5 },
];

export const VPP_SWARM: { id: string; lat: number; lng: number; ba: ISO }[] = [
  { id: 'vpp-bay', lat: 37.78, lng: -122.42, ba: 'CAISO' },
  { id: 'vpp-la', lat: 34.05, lng: -118.24, ba: 'CAISO' },
  { id: 'vpp-sd', lat: 32.71, lng: -117.16, ba: 'CAISO' },
  { id: 'vpp-sac', lat: 38.58, lng: -121.49, ba: 'CAISO' },
  { id: 'vpp-fresno', lat: 36.74, lng: -119.78, ba: 'CAISO' },
  { id: 'vpp-sj', lat: 37.34, lng: -121.89, ba: 'CAISO' },
  { id: 'vpp-oak', lat: 37.80, lng: -122.27, ba: 'CAISO' },
  { id: 'vpp-bk', lat: 35.37, lng: -119.02, ba: 'CAISO' },
  { id: 'vpp-rvr', lat: 33.95, lng: -117.40, ba: 'CAISO' },
  { id: 'vpp-anh', lat: 33.83, lng: -117.91, ba: 'CAISO' },
  { id: 'vpp-phl', lat: 39.95, lng: -75.16, ba: 'PJM' },
  { id: 'vpp-bal', lat: 39.29, lng: -76.61, ba: 'PJM' },
  { id: 'vpp-dc', lat: 38.90, lng: -77.04, ba: 'PJM' },
  { id: 'vpp-pgh', lat: 40.44, lng: -79.99, ba: 'PJM' },
  { id: 'vpp-cle', lat: 41.50, lng: -81.69, ba: 'PJM' },
  { id: 'vpp-col', lat: 39.96, lng: -82.99, ba: 'PJM' },
  { id: 'vpp-cin', lat: 39.10, lng: -84.51, ba: 'PJM' },
  { id: 'vpp-ind', lat: 39.77, lng: -86.16, ba: 'PJM' },
  { id: 'vpp-rch', lat: 37.54, lng: -77.43, ba: 'PJM' },
  { id: 'vpp-nrf', lat: 36.85, lng: -76.29, ba: 'PJM' },
  { id: 'vpp-nyc', lat: 40.71, lng: -74.00, ba: 'NYISO' },
  { id: 'vpp-buf', lat: 42.89, lng: -78.88, ba: 'NYISO' },
  { id: 'vpp-alb', lat: 42.65, lng: -73.76, ba: 'NYISO' },
  { id: 'vpp-roc', lat: 43.16, lng: -77.61, ba: 'NYISO' },
  { id: 'vpp-bos', lat: 42.36, lng: -71.06, ba: 'ISO-NE' },
  { id: 'vpp-prv', lat: 41.82, lng: -71.41, ba: 'ISO-NE' },
  { id: 'vpp-htf', lat: 41.76, lng: -72.69, ba: 'ISO-NE' },
  { id: 'vpp-chi', lat: 41.88, lng: -87.63, ba: 'MISO' },
  { id: 'vpp-mke', lat: 43.04, lng: -87.91, ba: 'MISO' },
  { id: 'vpp-mn', lat: 44.98, lng: -93.27, ba: 'MISO' },
  { id: 'vpp-stl', lat: 38.63, lng: -90.20, ba: 'MISO' },
  { id: 'vpp-det', lat: 42.33, lng: -83.05, ba: 'MISO' },
  { id: 'vpp-okc', lat: 35.47, lng: -97.52, ba: 'SPP' },
  { id: 'vpp-tul', lat: 36.15, lng: -95.99, ba: 'SPP' },
  { id: 'vpp-wic', lat: 37.69, lng: -97.34, ba: 'SPP' },
  { id: 'vpp-omh', lat: 41.26, lng: -95.93, ba: 'SPP' },
  // Texas VPP cluster — needed so ERCOT scenarios have local VPPs to dispatch
  { id: 'vpp-hou', lat: 29.76, lng: -95.37, ba: 'ERCOT' },
  { id: 'vpp-dfw', lat: 32.78, lng: -96.80, ba: 'ERCOT' },
  { id: 'vpp-aus', lat: 30.27, lng: -97.74, ba: 'ERCOT' },
  { id: 'vpp-sat', lat: 29.42, lng: -98.49, ba: 'ERCOT' },
  { id: 'vpp-elp', lat: 31.76, lng: -106.49, ba: 'ERCOT' },
  { id: 'vpp-cps', lat: 31.55, lng: -97.15, ba: 'ERCOT' },
];

export interface CriticalSite {
  id: string;
  lat: number;
  lng: number;
  label: string;
}

export const CRITICAL_SITES_BY_REGION: Record<string, CriticalSite[]> = {
  ERCOT: [
    { id: 'crit-hou', lat: 29.76, lng: -95.37, label: 'Houston Medical' },
    { id: 'crit-dal', lat: 32.78, lng: -96.80, label: 'Dallas Hospitals' },
    { id: 'crit-sat', lat: 29.42, lng: -98.49, label: 'San Antonio' },
    { id: 'crit-aus', lat: 30.27, lng: -97.74, label: 'Austin EMS' },
  ],
  CAISO: [
    { id: 'crit-sf', lat: 37.77, lng: -122.42, label: 'SF General' },
    { id: 'crit-oak', lat: 37.80, lng: -122.27, label: 'Oakland Trauma' },
    { id: 'crit-sj', lat: 37.34, lng: -121.89, label: 'SJ Hospitals' },
    { id: 'crit-la', lat: 34.05, lng: -118.24, label: 'LA Medical' },
  ],
  PJM: [
    { id: 'crit-dc', lat: 38.90, lng: -77.04, label: 'DC Medical' },
    { id: 'crit-bal', lat: 39.29, lng: -76.61, label: 'Baltimore Trauma' },
    { id: 'crit-phl', lat: 39.95, lng: -75.16, label: 'Philly Hospitals' },
    { id: 'crit-rch', lat: 37.54, lng: -77.43, label: 'Richmond EMS' },
  ],
};

export const CRITICAL_SITES: CriticalSite[] = CRITICAL_SITES_BY_REGION.ERCOT;
