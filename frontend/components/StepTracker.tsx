export type StepState = "pending" | "active" | "done" | "failed";

export interface Step {
    label: string;
    state: StepState;
    detail?: string;
}

const dotStyles: Record<StepState, string> = {
    pending: "border-zinc-300 bg-white text-zinc-400",
    active: "border-blue-500 bg-blue-50 text-blue-600",
    done: "border-emerald-500 bg-emerald-500 text-white",
    failed: "border-red-500 bg-red-500 text-white",
};

const lineStyles: Record<StepState, string> = {
    pending: "bg-zinc-200",
    active: "bg-zinc-200",
    done: "bg-emerald-500",
    failed: "bg-zinc-200",
};

const StepIcon = ({ state, index }: { state: StepState; index: number }) => {
    if (state === "done") {
        return (
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden>
                <path fillRule="evenodd" d="M16.7 5.3a1 1 0 0 1 0 1.4l-8 8a1 1 0 0 1-1.4 0l-4-4a1 1 0 1 1 1.4-1.4L8 12.6l7.3-7.3a1 1 0 0 1 1.4 0Z" clipRule="evenodd" />
            </svg>
        );
    }
    if (state === "failed") return <span className="text-xs font-bold">!</span>;
    if (state === "active") {
        return <span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />;
    }
    return <span className="text-xs font-medium">{index + 1}</span>;
};

export const StepTracker = ({ steps }: { steps: Step[] }) => {
    return (
        <ol className="flex w-full items-start">
            {steps.map((step, i) => (
                <li key={step.label} className="flex flex-1 flex-col items-center">
                    <div className="flex w-full items-center">
                        <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 ${dotStyles[step.state]}`}>
                            <StepIcon state={step.state} index={i} />
                        </span>
                        {i < steps.length - 1 && <span className={`mx-2 h-0.5 flex-1 rounded ${lineStyles[step.state]}`} />}
                    </div>
                    <div className="mt-2 w-full pr-2">
                        <p className={`text-sm font-medium ${step.state === "failed" ? "text-red-600" : step.state === "pending" ? "text-zinc-400" : "text-zinc-800"}`}>{step.label}</p>
                        {step.detail && <p className="text-xs text-zinc-500">{step.detail}</p>}
                    </div>
                </li>
            ))}
        </ol>
    );
};
