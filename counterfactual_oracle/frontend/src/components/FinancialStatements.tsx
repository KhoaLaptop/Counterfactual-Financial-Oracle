import React, { useState } from 'react';
import { FinancialReportData } from '../lib/types';
import { FileText, DollarSign, TrendingUp } from 'lucide-react';

interface FinancialStatementsProps {
    data: FinancialReportData;
}

const FinancialStatements: React.FC<FinancialStatementsProps> = ({ data }) => {
    const [activeTab, setActiveTab] = useState<'is' | 'bs' | 'cf'>('is');

    const formatCurrency = (value: number) => {
        if (value === undefined || value === null) return '-';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 0,
        }).format(value);
    };

    const TabButton = ({ id, label, icon: Icon }: { id: 'is' | 'bs' | 'cf', label: string, icon: any }) => (
        <button
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === id
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`}
        >
            <Icon size={16} />
            {label}
        </button>
    );

    return (
        <div className="card">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold">Financial Statements</h2>
                <div className="flex bg-gray-900 p-1 rounded-lg">
                    <TabButton id="is" label="Income Statement" icon={FileText} />
                    <TabButton id="bs" label="Balance Sheet" icon={DollarSign} />
                    <TabButton id="cf" label="Cash Flow" icon={TrendingUp} />
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-left">
                    <thead>
                        <tr className="border-b border-gray-800">
                            <th className="py-3 px-4 text-gray-400 font-medium">Line Item</th>
                            <th className="py-3 px-4 text-gray-400 font-medium text-right">Value</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                        {activeTab === 'is' && (
                            <>
                                <tr><td className="py-3 px-4">Revenue</td><td className="py-3 px-4 text-right font-medium">{formatCurrency(data.income_statement.Revenue)}</td></tr>
                                <tr><td className="py-3 px-4">Cost of Goods Sold</td><td className="py-3 px-4 text-right text-red-400">({formatCurrency(data.income_statement.CostOfGoodsSold)})</td></tr>
                                <tr className="bg-gray-800/50"><td className="py-3 px-4 font-medium">Gross Profit</td><td className="py-3 px-4 text-right font-bold">{formatCurrency(data.income_statement.GrossProfit)}</td></tr>
                                <tr><td className="py-3 px-4">Operating Expenses</td><td className="py-3 px-4 text-right text-red-400">({formatCurrency(data.income_statement.OpEx)})</td></tr>
                                <tr className="bg-gray-800/50"><td className="py-3 px-4 font-medium">EBITDA</td><td className="py-3 px-4 text-right font-bold text-blue-400">{formatCurrency(data.income_statement.EBITDA)}</td></tr>
                                <tr><td className="py-3 px-4">Depreciation & Amortization</td><td className="py-3 px-4 text-right text-red-400">({formatCurrency(data.income_statement.DepreciationAndAmortization)})</td></tr>
                                <tr><td className="py-3 px-4">EBIT</td><td className="py-3 px-4 text-right">{formatCurrency(data.income_statement.EBIT)}</td></tr>
                                <tr><td className="py-3 px-4">Interest Expense</td><td className="py-3 px-4 text-right text-red-400">({formatCurrency(data.income_statement.InterestExpense)})</td></tr>
                                <tr><td className="py-3 px-4">Taxes</td><td className="py-3 px-4 text-right text-red-400">({formatCurrency(data.income_statement.Taxes)})</td></tr>
                                <tr className="bg-gray-800/50"><td className="py-3 px-4 font-medium">Net Income</td><td className="py-3 px-4 text-right font-bold text-green-400">{formatCurrency(data.income_statement.NetIncome)}</td></tr>
                            </>
                        )}

                        {activeTab === 'bs' && (
                            <>
                                <tr className="bg-gray-900/50"><td colSpan={2} className="py-2 px-4 text-xs font-semibold text-gray-500 uppercase">Assets</td></tr>
                                <tr><td className="py-3 px-4 pl-8">Cash & Equivalents</td><td className="py-3 px-4 text-right">{formatCurrency(data.balance_sheet.Cash || 0)}</td></tr>
                                <tr className="bg-gray-800/30"><td className="py-3 px-4 font-medium">Total Assets</td><td className="py-3 px-4 text-right font-bold">{formatCurrency(data.balance_sheet.Assets.TotalAssets)}</td></tr>

                                <tr className="bg-gray-900/50"><td colSpan={2} className="py-2 px-4 text-xs font-semibold text-gray-500 uppercase">Liabilities</td></tr>
                                <tr><td className="py-3 px-4 pl-8">Short Term Debt</td><td className="py-3 px-4 text-right">{formatCurrency(data.balance_sheet.ShortTermDebt || 0)}</td></tr>
                                <tr><td className="py-3 px-4 pl-8">Long Term Debt</td><td className="py-3 px-4 text-right">{formatCurrency(data.balance_sheet.LongTermDebt || 0)}</td></tr>
                                <tr className="bg-gray-800/30"><td className="py-3 px-4 font-medium">Total Liabilities</td><td className="py-3 px-4 text-right font-bold">{formatCurrency(data.balance_sheet.Liabilities.TotalLiabilities)}</td></tr>

                                <tr className="bg-gray-900/50"><td colSpan={2} className="py-2 px-4 text-xs font-semibold text-gray-500 uppercase">Equity</td></tr>
                                <tr className="bg-gray-800/30"><td className="py-3 px-4 font-medium">Total Equity</td><td className="py-3 px-4 text-right font-bold">{formatCurrency(data.balance_sheet.Equity.TotalEquity)}</td></tr>
                            </>
                        )}

                        {activeTab === 'cf' && (
                            <>
                                <tr><td className="py-3 px-4">Net Income</td><td className="py-3 px-4 text-right">{formatCurrency(data.cash_flow.NetIncome)}</td></tr>
                                <tr><td className="py-3 px-4">Depreciation & Amortization</td><td className="py-3 px-4 text-right">{formatCurrency(data.cash_flow.Depreciation)}</td></tr>
                                <tr><td className="py-3 px-4">Change in Working Capital</td><td className="py-3 px-4 text-right">{formatCurrency(data.cash_flow.ChangeInWorkingCapital)}</td></tr>
                                <tr className="bg-gray-800/50"><td className="py-3 px-4 font-medium">Cash from Operations</td><td className="py-3 px-4 text-right font-bold">{formatCurrency(data.cash_flow.CashFromOperations)}</td></tr>

                                <tr><td className="py-3 px-4">CapEx</td><td className="py-3 px-4 text-right text-red-400">({formatCurrency(data.cash_flow.CapEx)})</td></tr>
                                <tr><td className="py-3 px-4">Cash from Investing</td><td className="py-3 px-4 text-right">{formatCurrency(data.cash_flow.CashFromInvesting)}</td></tr>

                                <tr><td className="py-3 px-4">Cash from Financing</td><td className="py-3 px-4 text-right">{formatCurrency(data.cash_flow.CashFromFinancing)}</td></tr>

                                <tr className="bg-gray-800/50"><td className="py-3 px-4 font-medium">Free Cash Flow</td><td className="py-3 px-4 text-right font-bold text-green-400">{formatCurrency(data.cash_flow.FreeCashFlow || 0)}</td></tr>
                            </>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default FinancialStatements;
