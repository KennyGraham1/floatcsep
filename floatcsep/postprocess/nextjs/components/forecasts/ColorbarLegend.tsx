'use client';

interface ColorbarLegendProps {
  vmin: number;
  vmax: number;
  title?: string;
}

// Magma256 color palette (matching Bokeh's Magma256 palette used in panel app)
const MAGMA_COLORS = [
  '#000004', '#010005', '#010106', '#010108', '#020109', '#02020b', '#02020d', '#03030f',
  '#030312', '#040414', '#050416', '#060518', '#06051a', '#07061c', '#08071e', '#090720',
  '#0a0822', '#0b0924', '#0c0926', '#0d0a29', '#0e0b2b', '#100b2d', '#110c2f', '#120d31',
  '#140d33', '#150e36', '#160e38', '#180f3a', '#19103c', '#1a103e', '#1c1141', '#1d1143',
  '#1e1245', '#201247', '#21134a', '#22134c', '#24144e', '#251451', '#271553', '#281555',
  '#2a1658', '#2b165a', '#2d175c', '#2e175f', '#301861', '#311863', '#331966', '#341968',
  '#361a6b', '#371a6d', '#391b6f', '#3a1b72', '#3c1c74', '#3d1c76', '#3f1d79', '#401d7b',
  '#421e7d', '#431e80', '#451f82', '#461f84', '#482087', '#492089', '#4b218b', '#4c218e',
  '#4e2290', '#4f2292', '#512395', '#522397', '#542499', '#55249c', '#57259e', '#5926a0',
  '#5a26a3', '#5c27a5', '#5d27a7', '#5f28aa', '#6029ac', '#6229ae', '#642ab1', '#652ab3',
  '#672bb5', '#692cb8', '#6a2cba', '#6c2dbc', '#6e2ebf', '#6f2ec1', '#712fc3', '#7330c5',
  '#7430c8', '#7631ca', '#7832cc', '#7a32ce', '#7b33d1', '#7d34d3', '#7f35d5', '#8035d7',
  '#8236d9', '#8437db', '#8637dd', '#8738e0', '#8939e2', '#8b3ae4', '#8d3ae6', '#8e3be8',
  '#903cea', '#923dec', '#933eee', '#953ef0', '#973ff2', '#9840f4', '#9a41f6', '#9c42f8',
  '#9d43fa', '#9f44fc', '#a145fd', '#a346ff', '#a447ff', '#a648ff', '#a84aff', '#aa4bff',
  '#ab4dfe', '#ad4efe', '#ae50fe', '#b051fe', '#b253fe', '#b354fd', '#b556fd', '#b657fc',
  '#b859fc', '#b95bfb', '#bb5cfb', '#bc5efa', '#be5ff9', '#bf61f9', '#c063f8', '#c264f7',
  '#c366f6', '#c467f5', '#c669f4', '#c76bf3', '#c86cf2', '#c96ef1', '#cb6ff0', '#cc71ef',
  '#cd73ed', '#ce74ec', '#cf76eb', '#d077e9', '#d179e8', '#d27ae7', '#d37ce5', '#d47de4',
  '#d57fe2', '#d680e1', '#d782df', '#d783dd', '#d885dc', '#d986da', '#da88d9', '#db89d7',
  '#db8bd5', '#dc8cd4', '#dd8ed2', '#de8fd0', '#de91cf', '#df92cd', '#e094cb', '#e095c9',
  '#e197c7', '#e198c6', '#e29ac4', '#e29bc2', '#e39dc0', '#e39ebf', '#e4a0bd', '#e4a1bb',
  '#e5a3b9', '#e5a4b7', '#e6a6b5', '#e6a7b3', '#e7a9b1', '#e7aaaf', '#e7acad', '#e8adab',
  '#e8afa9', '#e9b0a7', '#e9b2a5', '#e9b3a4', '#eab5a2', '#eab6a0', '#eab89e', '#ebb99c',
  '#ebbb9a', '#ebbc98', '#ecbe96', '#ecbf94', '#ecc192', '#edc291', '#edc48f', '#edc58d',
  '#eec78b', '#eec889', '#eeca87', '#eecb86', '#eecd84', '#efce82', '#efd080', '#efd17f',
  '#efd37d', '#f0d47b', '#f0d67a', '#f0d778', '#f0d977', '#f1da75', '#f1dc74', '#f1dd72',
  '#f1df71', '#f1e06f', '#f2e26e', '#f2e36d', '#f2e56b', '#f2e66a', '#f2e869', '#f3e968',
  '#f3eb66', '#f3ec65', '#f3ee64', '#f3ef63', '#f3f162', '#f4f261', '#f4f45f', '#f4f55e',
  '#f4f75d', '#f4f85c', '#f5fa5b', '#f5fb5a', '#f5fc59', '#f6fe58', '#f6ff57', '#f7ff56'
];

export default function ColorbarLegend({ vmin, vmax, title = 'log10 λ' }: ColorbarLegendProps) {
  return (
    <div className="bg-surface p-4 rounded-lg border border-border">
      <div className="flex items-center gap-3">
        <span className="text-xs text-gray-400 font-mono w-16 text-right">{vmin.toFixed(2)}</span>
        <div className="flex-1 h-8 rounded border border-border" style={{
          background: `linear-gradient(to right, ${MAGMA_COLORS.join(', ')})`,
        }} />
        <span className="text-xs text-gray-400 font-mono w-16">{vmax.toFixed(2)}</span>
      </div>
      <div className="text-center mt-2">
        <span className="text-xs text-gray-400">{title}</span>
      </div>
    </div>
  );
}
