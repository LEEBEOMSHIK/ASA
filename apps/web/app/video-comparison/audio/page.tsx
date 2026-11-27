import { AudioComparison } from "../../../components/audio-comparison";

type SampleParams = { left?: string | string[]; right?: string | string[] };

export default async function AudioComparisonPage({ searchParams }: { searchParams: Promise<SampleParams> }) {
  const { left, right } = await searchParams;
  return <AudioComparison initialLeft={typeof left === "string" ? left : ""}
    initialRight={typeof right === "string" ? right : ""} />;
}
